from openai import OpenAI
from time import sleep
### Might need to actually retrieve the assistant each time, not sure

class Assistant:
    def __init__(self) -> None:
        self.client = OpenAI()
        self.assistant = self.client.beta.assistants.create(
            instructions = """
                            You are a personal restaurant expert. When asked a 
                            question, check the provided csv file to answer the question.
                          """,
            name = "Restaurant Expert",
            tools = [{"type": "code_interpreter"}],
            model = "gpt-3.5-turbo",
            file_ids = []
        )
        self.thread = self.client.beta.threads.create()
        self.assistant_file = None

    def use_file(self, file: str):
        """
        Attatch file to assistant

        Args:
            file (str): path to the file
        """
        self.assistant_file =   self.client.beta.assistants.files.create(
                                assistant_id=self.assistant.id,
                                file_id=file
                                )
    
    def use_prompts(self, prompts: list):
        """
        Add all the prompts to the thread as messages.

        Args:
            prompts (list): A list of strings containing all the prompts
        """
        for prompt in prompts:
            self.client.beta.threads.messages.create(
                self.thread.id,
                role = "user",
                content = prompt,
                # file_ids = [self.assistant_file.id]
                )
            
    def run(self):
        self.run = self.client.beta.threads.runs.create(
            thread_id = self.thread.id,
            assistant_id = self.assistant.id
            )
    
    def get_result(self):
        # some delay
        run = self.client.beta.threads.runs.retrieve(run_id=self.run.id, thread_id=self.thread.id)

        messages = self.client.beta.threads.messages.list(self.thread.id)
        for index, message in enumerate(messages.data):
            sleep(20)
            last_message = messages.data[0]
            response = last_message.content[0].text.value
            print(index)
            print(message.role[1], " : " , message.content[0].text.value)
            print(message.role[0], " : ", response)
            print("---------------------------------------")


assistant = Assistant()
assistant.use_prompts(prompts=["How old are you?", "What is your purpose?"])
run = assistant.run()
print(assistant.get_result())



