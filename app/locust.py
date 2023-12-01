from locust import HttpUser, task, between

# to run: locust -f locustfile.py

class WebsiteUser(HttpUser):
    wait_time = between(1, 2.5)

    @task
    def delete_all_users(self):
        self.client.delete("/users")

    @task
    def delete_all_experts(self):
        self.client.delete("/experts")

    @task
    def delete_all_chats(self):
        self.client.delete("/chats")

    @task
    def delete_all_docs(self):
        self.client.post("/docs/deleteall")

    @task
    def create_user(self):
        user_data = {
            "email": "test@example.com",
            "name": "Test User",
            "role": "admin",
            "password": "password",
        }
        self.client.post("/users", json=user_data)

    @task
    def get_user(self):
        # Note: You'll need to replace 'user_id' with an actual user ID
        self.client.get("/users/{user_id}")

    @task
    def update_user(self):
        # Note: You'll need to replace 'user_id' with an actual user ID
        user_data = {
            "email": "steve@messina.com",
        }
        self.client.patch("/users/{user_id}", json=user_data)

    @task
    def get_all_users(self):
        self.client.get("/users")

    #@task
    #def load_experts(self):
    #    # Note: You'll need to replace 'filename' with an actual file path
    #    data = {"filename": "{filename}"}
    #    self.client.post("/experts/load", params=data)

    @task
    def create_expert(self):
        expert_data = {
            "name": "Expert User",
            "role": "expert",
            "image": "http://placekitten.com/g/100/100",
            "objective": "Provide expert advice",
            "prompt": "Ask me anything",
        }
        self.client.post("/experts", json=expert_data)

    @task
    def update_expert(self):
        # Note: You'll need to replace 'expert_id' with an actual expert ID
        expert_data = {
            "name": "Jane Brain",
        }
        self.client.patch("/experts/{expert_id}", json=expert_data)

    @task
    def get_expert(self):
        # Note: You'll need to replace 'expert_id' with an actual expert ID
        self.client.get("/experts/{expert_id}")

    @task
    def get_all_experts(self):
        self.client.get("/experts")


    @task
    def create_chat(self):
        # Note: You'll need to replace 'user_id' and 'expert_id' with actual IDs
        chat_data = {
            "name": "Chat Room",
            "user_id": "{user_id}",
            "expert_id": "{expert_id}",
        }
        self.client.post("/chats", json=chat_data)

    @task
    def get_chat_for_user(self):
        # Note: You'll need to replace 'user_id' with an actual user ID
        self.client.get("/chats/user/{user_id}")

    @task
    def get_messages(self):
        # Note: You'll need to replace 'chat_id' with an actual chat ID
        self.client.get("/chats/{chat_id}/messages")

    @task
    def get_all_chats(self):
        self.client.get("/chats")

    @task
    def upload_documents(self):
        # Note: You'll need to replace 'file1' and 'file2' with actual file paths
        files = [
            ('files', open('{file1}', 'rb')),
            ('files', open('{file2}', 'rb')),
        ]
        self.client.post("/docs/upload", files=files)

    @task
    def upload_pdf_document_from_url(self):
        doc = {"filename": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"}
        self.client.post("/docs/upload_from_url", json=doc)

    @task
    def upload_excel_document_from_url(self):
        doc = {"filename": "https://file-examples.com/wp-content/storage/2017/02/file_example_XLS_10.xlsx"}
        self.client.post("/docs/upload_from_url", json=doc)

    @task
    def get_document(self):
        # Note: You'll need to replace 'document_id' with an actual document ID
        self.client.get("/docs/{document_id}")

    @task
    def get_all_documents(self):
        self.client.get("/docs/all")
