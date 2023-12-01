from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic import EmailStr
import inspect
from redis_om import JsonModel, Migrator, EmbeddedJsonModel

# We use the to decorate the xxxUpdate schemas to allow us to do PUT/PATCH
# and only supply the new data fields in a dict
# Note: that the schemas now don't all inherit from xxxBase, to make this more sensible
def optional(*fields):
    """Decorator function used to modify a pydantic model's fields to all be optional.
    Alternatively, you can  also pass the field names that should be made optional as arguments
    to the decorator.
    Taken from https://github.com/samuelcolvin/pydantic/issues/1223#issuecomment-775363074
    """   
    def dec(_cls):
        for field in fields:
            _cls.__fields__[field].required = False
        return _cls

    if fields and inspect.isclass(fields[0]) and issubclass(fields[0], BaseModel):
        cls = fields[0]
        fields = cls.__fields__
        return dec(cls)

    return dec


# TODO: remove the "pk" primary index from docs
class MyConfig:
    artibrary_types_allowed = True
    underscore_attrs_are_private = True
    orm_model = True


class ToolInput(BaseModel):
    question: str = Field()


# ###################################################### SKILLS

# A model for a langchain OpenAI Functions tool that wraps a function that is loaded from an external module
class Skill(JsonModel):
    name: str = Field(index=True, full_text_search=True, default="Skill")
    description: str = "useful for when you need to answer questions about ..."
    args_schema: str = ""
    env_vars: list[str] = []
    image: str = "http://placekitten.co/100/100"
    modules: list[str] = []
    code: str = ""



# Pydantic model for Google sign-in
class GoogleSignIn(BaseModel):
    id_token: str


# JWT Token
class Token(BaseModel):
    access_token: str
    token_type: str


# Encode the email in the JWT Token custom data in order to lookup the User
class TokenData(BaseModel):
    email: str | None = None


class Role(str, Enum):
    admin = 'admin'
    user = 'user'


# UserRecord in JWT Token
class UserRecord(BaseModel):
    uid: str | None = None
    name: str | None = None
    email: str | None = None
    role: Role | None = None


class LLMToken(JsonModel):
#    timestamp: str = str(Field(default_factory=datetime.now))
    llm_model: str = ""  # which llm were we using
    purpose: str = ""  # which function were we executing, e.g. doc upload
    usage: str = ""  # which sub process, e.g. embedding
    total_tokens: int = 0  # total tokens used
    prompt_tokens: int = 0  # subset of tokens used for prompts
    completion_tokens: int = 0  # subset of tokens used for completion
    total_usd_cost: float = 0.0  # total usd cost for these tokens


# ###################################################### DOCS
class DocType(str, Enum):
    file = 'file'
    url = 'url'


class DocBase(JsonModel):
    filename: str = Field(index=True, full_text_search=True)
    type: DocType = DocType.file
    owner: str = "shared"  # shared or expert_id
    summary: str = ""  # User supplied description of the file contents

    class Config:
        orm_mode = True
        use_enum_values = True
        artibrary_types_allowed = True
        underscore_attrs_are_private = True        


class DocCreate(DocBase):
    pass


@optional
class DocUpdate(DocBase):
    pass


class Doc(DocBase):
    index_name: str = ""
    keys: list[str] = []
    pass


# ###################################################### EXPERTS

class ExpertBase(JsonModel):
    name: str = Field(index=True, full_text_search=True)
    role: str 
    image: str = "http://placekitten.com/g/200/300"
    objective: str = ""
    prompt: str = ""
    tone: str = ""

    class Config:
        orm_mode = True
        use_enum_values = True
        artibrary_types_allowed = True
        underscore_attrs_are_private = True        


class ExpertCreate(ExpertBase):
    pass

@optional
class ExpertUpdate(ExpertBase):
    pass


class Expert(ExpertBase):
    owner: str = "basic"  # template agents = plan('basic','pro','enterprise'), or user owned agents = user_id - when a user is created, the shared experts are duplicated into his domain
    docs: list[Doc] = []
    pass


class SummarizedDoc(Doc):
    _filename: str = Field(alias='filename', default="")
    _type: DocType = Field(alias='type', default=DocType.file)
    _summary: str = Field(alias='summary', default="")


class SummarizedExpert(Expert):
    _name: str = Field(alias='name', default="")
    _role: Role = Field(alias='role', default=Role.user)
    _image: str = Field(alias='image', default="")
    _objective: str = Field(alias='objective', default="")
    _prompt: str = Field(alias='prompt', default="")
    _tone: str = Field(alias='tone', default="")
    _docs: list[SummarizedDoc] = Field(alias='docs', default=[])

# ###################################################### BOOKMARKS


class BookmarkBase(JsonModel):
    user_id: str
    message_id: str

    class Config:
        orm_mode = True
        use_enum_values = True
        artibrary_types_allowed = True
        underscore_attrs_are_private = True        


class BookmarkCreate(BookmarkBase):
    text: str
    pass


@optional
class BookmarkUpdate(BookmarkCreate):
    pass


class Bookmark(BookmarkCreate):
    pass 

# ###################################################### CHATS


class ChatBase(JsonModel):
    name: str = Field(index=True, full_text_search=True)
        
    class Config:
        orm_mode = True
        use_enum_values = True
        artibrary_types_allowed = True
        underscore_attrs_are_private = True        
  
        
class ChatCreate(ChatBase):
    user_id: str = Field(index=True)
    expert_id: str = Field(index=True)
    pass


@optional
class ChatUpdate(ChatBase):
    pass


class Chat(ChatBase):
    # TODO: move these to ChatCreate so they can't be altered later
    user_id: str = Field(index=True)
    expert_id: str = Field(index=True)
    memory_id: str = ""
    # TODO: Does the default expert go into participants too? What happens when we try remove them?
    participants: list[str] = []
    bookmarks: list[str] = []
    messages: list[str] = [] # This gets populated from the memory store on get messages
    pass


# ###################################################### USERS


class Plan(str, Enum):
    basic = 'basic'
    pro = 'pro'
    enterprise = 'enterprise'


class Subscription(EmbeddedJsonModel):
    stripe_price_id: str = ""
    balance: float = 0.0
    plan: Plan = Plan.basic


class UserBase(JsonModel):
    uid: Optional[str] = Field(index=True, full_text_search=True)
    email: EmailStr = Field(index=True, full_text_search=True)
    name: str = Field(index=True, full_text_search=True)
    role: Role = Field('user', alias='role')
    image: str = "http://placekitten.com/g/500/500"
    business_profile: str = ""
    disabled: bool | None = False
    subscription: Subscription

    class Config:
        orm_mode = True
        use_enum_values = True
        artibrary_types_allowed = True
        underscore_attrs_are_private = True        


class UserCreate(UserBase):
    password: Optional[str] = ""
    pass


# @optional makes all the fields optional for PUT/PATCH so we only have to send a subset of changed data
@optional
class UserUpdate(UserBase):
    pass


class User(UserBase):
    chat_sessions: list[Dict] = []
    llm_token_usage: list[LLMToken] = []
    experts: list[Expert] = []    
    pass




# TODO: Uncomment this for indexing. Only need to run migrator if we need to create indexes for find() etc.
Migrator().run()