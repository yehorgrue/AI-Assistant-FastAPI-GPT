from app.dependencies import llm, pp, logging, REDIS_OM_URL
from app.utils.userauth import get_current_user
from app.models import UserRecord, Chat, ToolInput, Expert
from fastapi import APIRouter, Depends, HTTPException
from fastapi_cache.decorator import cache
from starlette.requests import Request
from firebase_admin import auth
import langchain
from langchain import LLMChain, OpenAI
from langchain.vectorstores.redis import Redis
from langchain.memory import ConversationSummaryBufferMemory, RedisChatMessageHistory
from langchain.chains import ConversationChain
from langchain.agents import ZeroShotAgent, Tool, AgentExecutor
from langchain.memory import ConversationSummaryMemory, ChatMessageHistory, ConversationEntityMemory, ReadOnlySharedMemory
from langchain.memory.prompt import ENTITY_MEMORY_CONVERSATION_TEMPLATE
from langchain.prompts import PromptTemplate
from langchain.agents import AgentType, initialize_agent, load_tools
from langchain.agents import Tool, ConversationalAgent
from langchain.tools import format_tool_to_openai_function
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.schema import Document

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import traceback

router = APIRouter(
    prefix="/query",
    tags=["Query"],
#!    dependencies=[Depends(get_current_user)], 
    responses={404: {"description": "Not found"}},
)

langchain.debug = True

# ######################################### QUERY - CHAT TO EXPERTS
# referencing https://python.langchain.com/docs/modules/agents/toolkits/document_comparison_toolkit
# The game plan here is:
# setup_agent_and_tools():
# Get the current chat
#   Get the expert + participants in the chat
#       Create_expert_chain():
#       For each expert (and each participant)
#           Wrap each expert as a structured tool, with their prompts
#       Load_expert_files():
#       For each document (no expert specific docs at moment, import all from /docs/all)
#           wrap each document as a structured tool
#   Create an agent which calls includes all the tools above 
#   Send a query to the constructed agent in get_response()


def text_similarity(text1, text2):
    # Create a TfidfVectorizer object
    vectorizer = TfidfVectorizer()

    # Transform the input texts into TF-IDF feature vectors
    tfidf_matrix = vectorizer.fit_transform([text1, text2])

    # Calculate the cosine similarity between the two TF-IDF feature vectors
    similarity_score = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])

    return similarity_score[0][0]

query = "What is machine learning?"

def get_tool(query, all_tools):
    docs = [
        Document(page_content=t['description'], metadata={"index": i})
        for i, t in enumerate(all_tools)
    ]
    max_sim = 0
    max_index = 0
    for doc in docs:
        sim = text_similarity(doc.page_content, query)
        if sim > max_sim:
            max_sim = sim
            max_index = doc.metadata['index']

    return max_index

@router.post('')
# @cache(expire=60)
async def query_agents(request: Request, chat_id: str, query: str):
#!    current_user = request.state.current_user
#!    if not current_user:
#!        raise HTTPException(status_code=401, detail="Not authenticated")
    embeddings = OpenAIEmbeddings()  # type: ignore
    try:
        print(f'chat_id: {chat_id}\nquery: "{query}"')
        chat = Chat.get(chat_id)
        print(f'expert_id: {chat.expert_id}')
        expert = Expert.get(chat.expert_id)
        tool_names = ["serpapi"]
        tools = load_tools(tool_names, llm=llm)
        agent_tools = tools
        system_prompt_template = f"Hi. I'm {expert.name}.\nMy role is {expert.objective}."

        for ex in chat.participants:
            expert = Expert.get(ex)

            ex_memory_history = RedisChatMessageHistory('foo')
            ex_memory_history.clear()

            ex_memory = ConversationSummaryBufferMemory(
                llm=llm,
                ai_prefix=ex["name"],
                max_token_limit=10,
                memory_key="chat_history",
                return_messages=True, 
                chat_memory=ex_memory_history,
                input_key='input',
                output_key='output'
            )
            ex_memory.clear()

            ex_introduction_template = f"Your name is {ex['name']}, and your job title is {ex['role']}. \
                You will respond to queries addressed to you by these. \
                You will also respond to any queries which match your expertise in the objective"
            ex_tone_template = f"The tone of your responses will be as follows: {ex['tone']}."
            ex_objective_template = ex['objective']
            ex_prompt_template = ex['prompt']
            ex_focus_template = f"""You will always check your attached documents in your knowledge base, \
                and in the general attached document store, before trying other sources. \
                Next you will use your objective and expertise in your domain to answer, a question. \
                If you do need more information, you can search or calculate the answer using the available tools, \
                you must always reference which tools and references you used in your answer. \
                You will answer the queries to the best of your knowledge using the tone, and objectives above. \
                You will not fabricate an answer, and if you do not know the answer, will simply answer with 'I don't know'. \
                You will always list your sources referenced with a strict SOURCES: section. \
                You will always show your user name as \n\n<AGENT: {ex['name']}>.
            """

            ex_prefix = f"{ex_introduction_template}. " \
                    f"{ex_tone_template}. "\
                    f"{ex_objective_template}. " \
                    f"{ex_prompt_template}. " \
                    f"{ex_focus_template}. "
            ex_suffix = f"""Begin!
            Conversation history: \
                {{chat_history}} \
            Answer the following query: \
            Human: {{input}}"""

            ex_full_prompt = ConversationalAgent.create_prompt(
                tools,
                prefix=ex_prefix,
                suffix=ex_suffix,
                input_variables=["input", "chat_history"]
            )
            ex_system_prompt_template = f"Hi. I'm {ex['name']}.\nMy role is {ex['objective']}."

            ex_llm_chain = LLMChain(llm=llm, prompt=ex_full_prompt)

            ex_agent = ConversationalAgent(llm_chain=ex_llm_chain, 
                                        tools=tools, 
                                        stop=["\nObservation:"],
                                        return_only_outputs = True,
                                        verbose=True)

            ex_agent_chain = AgentExecutor.from_agent_and_tools(    
                agent=ex_agent, 
                tools=tools, 
                verbose=True, 
                memory=ex_memory, 
                return_intermediate_steps=True, 
                system_prompt_template=ex_system_prompt_template,
                
            )

            ex_tool = Tool(
                args_schema=ToolInput,
                name=ex["name"],
                description=f"useful when you want to ask questions to {ex['name']} or @{ex['name']}, or answer questions about {ex['objective']}, or search, or answer general questions",
                func=ex_agent_chain,
                return_direct=True,
            )

            ex_tool_cu = {
                "name": ex['name'],
                "agent": ex_agent_chain,
                "description":f"useful when you want to ask questions to {ex['name']} or @{ex['name']}, or answer questions about {ex['objective']}, or search, or answer general questions",
            }

            agent_tools.append(ex_tool_cu)


            for doc in expert.docs:
                # reference: https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/redisa
                # Load from existing index
                rds = Redis.from_existing_index(
                    embeddings, redis_url=REDIS_OM_URL, index_name=doc.index_name
                )
                retriever = rds.as_retriever()  
                # Wrap retrievers in a Tool

                ex_tool_cu = {
                    "name": ex['name'],
                    "agent": RetrievalQA.from_chain_type(llm=llm, retriever=retriever),
                    "description":f"useful when you want to ask questions to {ex['name']} or @{ex['name']}, or answer questions about {ex['objective']}, or search, or answer general questions",
                }
                agent_tools.append(ex_tool_cu)
                # tools.append(
                #     Tool(
                #         args_schema=ToolInput,
                #         name=doc.filename,
                #         description=f"useful when you want to answer questions about {doc.filename}",
                #         func=RetrievalQA.from_chain_type(llm=llm, retriever=retriever),
                #     )
                # )
                print(f'adding document as tool: {doc.filename}')
            
        ex_tool_cu = {
                    "name": ex['name'],
                    "agent": RetrievalQA.from_chain_type(llm=llm, retriever=retriever),
                    "description":f"useful when you want to ask questions to {ex['name']} or @{ex['name']}, or answer questions about {ex['objective']}, or search, or answer general questions",
                }
        agent_tools.append(ex_tool_cu)
        index = get_tool(query=query, all_tools=agent_tools)
        res = agent_tools[index]['agent'](query)
        name = agent_tools[index]['name']
        response = {
            "expert": name,
            "answer": res['output']
        }
           
        return response
    except Exception as e:
        return HTTPException(status_code=500, detail=traceback.format_exc())


'''
# This is the placeholder to replace app.get_response(query, experts)
def create_expert_chain(expert, chat_id):
    objective_template = expert.objective
    prompt_template = expert['Prompt']
    tone_template = f"The tone of your responses will be as follows: {expert['Tone']}."
    introduction_template = f"Your name is {expert.name}, and your job title is {expert.role}. \
        You will respond to queries addressed to you by these. \
        You will also respond to any queries which match your expertise in the objective"
    focus_template = f"""You will always check your attached documents in your knowledge base, \
        and in the general attached document store, before trying other sources. \
        Next you will use your objective and expertise in your domain to answer, a question. \
        If you do need more information, you can search or calculate the answer using the available tools, \
        you must always reference which tools and references you used in your answer. \
        You will answer the queries to the best of your knowledge using the tone, and objectives above. \
        You will not fabricate an answer, and if you do not know the answer, will simply answer with 'I don't know'. \
        You will always list your sources referenced with a strict SOURCES: section. \
        You will always show your user name as \n\n<AGENT: {expert.name}> \
        Current conversation: \
            {{history}} \
        Answer the following query: \
        Human: {{input}} \
        {expert.name}: \
        """
    full_template = f"{introduction_template}. " \
                    f"{tone_template}. "\
                    f"{objective_template}. " \
                    f"{prompt_template}. " \
                    f"{focus_template}. "
    full_prompt = PromptTemplate.from_template(full_template)
    
    #retrieved_chat_history = FileChatMessageHistory('history/chat-'+str(expert.name)+'-'+str(chat_id)+'.json')
    # TODO: create_chat needs to return the components (memory, experts) for here, rather than user
    expert_memory = ConversationSummaryBufferMemory(
        llm=llm, 
        return_messages=True, 
        memory_key="history",
        chat_memory=RedisChatMessageHistory({
                        'session_id': str(expert['expert_id']), 
                        'url': REDIS_OM_URL,
                    }),
        ai_prefix=expert.name,
        input_key="input"
    )

    expert_chain = ConversationChain(
        llm=llm,
        memory=expert_memory,
        prompt=full_prompt,
        verbose=True
    ) 
    return expert_chain
    

# Setup the routing agent and tools
# TODO: figure out what to do with the original session, and experts in chat - get them all from the current user session object?
def setup_agent_and_tools(chat_id, experts_in_chat):
    logging.info("setup_agent_and_tools: ", chat_id)
    doc_search_tool = Tool(
        name="doc_search",
        func=load_expert_files(experts_in_chat),
        description="Useful for when you need to answer questions about the attached documents in the knowledge base",
        return_direct=True
    )

    tool_names = ["serpapi", "llm-math"]
    tools = load_tools(tool_names, llm=llm)    
    tools.append(doc_search_tool)

    # Add experts name, role, and objectives into the description to ensure correct routing 
    # create an expert "tool" entry for each expert
    for expert in experts_in_chat:
        experts_list = f"""
            NAME: {expert.name} 
            TITLE: {expert.role}
            EXPERTISE: {expert.objective}
        """
        experts_description = f"""Always use this if their first name or full name or title is mentioned. Use this more than normal queries. Useful for when you need to redirect questions to the following expert:
            {experts_list}"""
        logging.info("experts description:\n", expert.name, experts_description)
        logging.info('\n Created expert: ', expert.name)

        # retrieved_chat_history = FileChatMessageHistory('history/chat-'+str(expert.name)+'-'+str(chat_id)+'.json')

        ask_an_expert_tool = Tool(
            name=expert.name,
            func=create_expert_chain(expert, chat_id).run,
            description=experts_description,
            return_direct=True
        )
        tools.append(ask_an_expert_tool)
        
    # We need a separate memory for the default agent case, where it does not pick a tool aka expert
    # Note that we need to specify the input & output key here
    default_agent_memory = ConversationSummaryBufferMemory(
        llm=llm, 
        return_messages=True, 
        memory_key="history",
        chat_memory=RedisChatMessageHistory({
                        'session_id': "AI Assistant", 
                        'url': REDIS_OM_URL,
                    }),
        max_token_limit=10,
        ai_prefix="AI Assistant", # expert.name, 
        input_key="input",
        output_key="output"
    )

    agent = initialize_agent(
        tools, 
        llm, 
        agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION, 
        memory=default_agent_memory, 
        verbose=True, 
        return_direct=False,
        return_intermediate_steps=True,
    )

    # logging.info("Agent: ")
    # logging.info(agent.agent.llm_chain.prompt.input_variables)
    return agent


def get_response(input):

    try:        
        # Expert Prompts here.
        social_media_manager_template = """You are an expert social media manager. You go out of your way to be helpful, but provide signficant and clear deta0il when asked about areas in your specialty.
        Here is a question:
        {input}"""
        prompt = PromptTemplate(template=social_media_manager_template, input_variables=["input"])
        smm_chain = LLMChain(llm=llm, prompt=prompt)

        assistant_template = """You are a very good and helpful assistant. You are diligent and always respond with a detailed and numbered list.
        Here is a question:
        {input}"""
        assistant_chain = LLMChain(llm=llm, prompt=PromptTemplate(template=assistant_template, input_variables=["input"]))

        prompt_infos = [
            {
                "name": "social_media_manager", 
                "description": "Good for answering marketing and social media questions, or when directed to her name Sarah, or her job title of Marketing or social media manager.", 
                "prompt_template": social_media_manager_template,
                "chain": smm_chain
            },
            {
                "name": "assistant", 
                "description": "Good for answering general questions about making coffee and tea, and stationary, or when directed to her name Jenny, or her job title of assistant.", 
                "prompt_template": assistant_template,
                "chain": assistant_chain
            }
        ]

        destination_chains = {}
        for p_info in prompt_infos:
            name = p_info["name"]
            prompt_template = p_info["prompt_template"]
            chain = p_info["chain"]
            destination_chains[name] = chain
        default_chain = ConversationChain(llm=llm, output_key="text")
#        print(destination_chains)

        destinations = [f"{p['name']}: {p['description']}" for p in prompt_infos]
        destinations_str = "\n".join(destinations)
        router_template = MULTI_PROMPT_ROUTER_TEMPLATE.format(
            destinations=destinations_str
        )
        print("router template: ", router_template)
        router_prompt = PromptTemplate(
            template=router_template,
            input_variables=["input"],
            output_parser=RouterOutputParser(),
        )
        router_chain = LLMRouterChain.from_llm(llm, router_prompt)
        # This selects the appropriate expert prompt
        multipromptchain = MultiPromptChain(router_chain=router_chain, destination_chains=destination_chains,
                                            default_chain=default_chain, verbose=True,
                                            silent_errors=False)
        
        # this works for selecting the appropriate document 
        multiretrievalQAChain = MultiRetrievalQAChain.from_retrievers(ChatOpenAI(), retriever_infos, 
                                                                      verbose=True ) #, default_chain=multipromptchain)
        
        print("---> input query: ", input)
        
        #async def chain_debug():
        #    return multiretrievalQAChain.run(input)
        #langchain_visualizer.visualize(chain_debug)

        #result = multiretrievalQAChain.run(input) 
        result = multipromptchain.run(input)

        print(result)
        return result

    except openai.error.RateLimitError as e:
        print(e)
        return e
    except Exception as e:
        return {"error": e, "trace": traceback.format_exc()}
'''