from openai import OpenAI
from openai import AssistantEventHandler
from typing_extensions import override
from time import sleep
### Might need to actually retrieve the assistant each time, not sure

class Assistant:
    def __init__(self) -> None:
        self.client = OpenAI()
        self.assistant = self.client.beta.assistants.create(
            instructions = """
                            You are a personal restaurant expert. When asked a 
                            question, check the provided file to answer the question.
                            Answer questions in one sentence and do not make up facts.
                            Do not suggest to make a reservation.
                          """,
            name = "Restaurant Expert",
            tools = [{"type": "code_interpreter"}, {"type": "retrieval"}],
            model = "gpt-3.5-turbo",
            # file_ids = []
        )
        self.thread = self.client.beta.threads.create()
        self.assistant_file = None

    def use_file(self, file: str):
        """
        Attatch file to assistant

        Args:
            file (str): path to the file
        """
        file__ = self.client.files.create(file=open(file, "rb"),purpose="assistants")
        self.assistant_file =   self.client.beta.assistants.files.create(
                                assistant_id=self.assistant.id,
                                file_id=file__.id)
    
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

            
assistant = Assistant()
assistant.use_file("/Users/jurianonderwater/Downloads/RestaurantReviews.json")
assistant.use_prompts(prompts=["Show me the first restaurant entry (excluding the column headers)"])
assistant.run()
sleep(10)
# my_assistant = assistant.client.beta.assistants.retrieve("asst_o53Sm9RfC4aDo6rATWyUJzmg")
# my_thread = assistant.client.beta.threads.retrieve("thread_3b8KBvDvkmn8yF8tZ7H5ebIg")
my_thread = assistant.client.beta.threads.retrieve(assistant.thread.id)

messages = assistant.client.beta.threads.messages.list(thread_id=my_thread.id)

for thread_message in messages.data:
    # Iterate over the 'content' attribute of the ThreadMessage, which is a list
    for content_item in thread_message.content:
        # Assuming content_item is a MessageContentText object with a 'text' attribute
        # and that 'text' has a 'value' attribute, print it
        print(content_item.text.value)

# # print(assistant.client.beta.threads.messages.list(assistant.thread.id))
# with assistant.client.beta.threads.runs.create_and_stream(
#   thread_id=my_thread.id,
# #   assistant_id=assistant.assistant.id,
#   assistant_id=my_assistant.id,
#   event_handler=AssistantEventHandler(),
# ) as stream:
#   stream.until_done()



