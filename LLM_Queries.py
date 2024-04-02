from openai import OpenAI
from openai import AssistantEventHandler
from typing_extensions import override
from time import sleep

class Assistant:
    def __init__(self, asst_id: str, thread_id: str) -> None:
        self.client = OpenAI()
        if asst_id != None:
            self.assistant = self.client.beta.assistants.retrieve(asst_id)
        else:
            self.assistant = self.client.beta.assistants.create(
                instructions = """
                            You are a restaurant virtual assistant chatting with a user.
You can access a restaurant dataset (json file) to retrieve information about restaurants and their reviews. You may incorporate information from user reviews or your own general knowledge in your replies, but DO NOT make up facts about restaurants. Do not repeat yourself. You cannot propose reservations.

In your response, first accurately tell the user what query you have searched for (if you have searched for anything), then tell the user the result.

If you did not check the json file, even though the user made a restaurant request, you should tell the user that you couldn't help them with that request.

The number of returned results might not match exactly what you have searched for. In this case, do not make up additional restaurants and only report returned results.

The json file is formatted as a dictionairy with the restaurant name as the key, and the value is a list of reviews.
                          """,
            name = "Restaurant Expert",
            tools = [{"type": "code_interpreter"}, {"type": "retrieval"}],
            model = "gpt-4-turbo-preview",
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
assistant.use_file("/Users/jurianonderwater/Downloads/truncated-reviews.json")
# assistant.use_prompts(prompts=["Which different restaurants can be considered 'cost effective', or 'cheap', based on the reviews. Search until you find 5"])
assistant.use_prompts(prompts=["Choose five different restaurants in the json file and list whether the reviews for that restaurant say anything about them being family friendly."])
print("Starting run ...\n__________________________________________________________________________________")
assistant.run()
while True:
    sleep(3)
    # my_assistant = assistant.client.beta.assistants.retrieve("asst_o53Sm9RfC4aDo6rATWyUJzmg")
    # my_thread = assistant.client.beta.threads.retrieve("thread_3b8KBvDvkmn8yF8tZ7H5ebIg")
    my_thread = assistant.client.beta.threads.retrieve(assistant.thread.id)
    run_status = assistant.client.beta.threads.runs.retrieve(
        thread_id=assistant.thread.id,
        run_id=assistant.run.id
    )
    if run_status.status == "completed":
        print("Run is Completed")
        messages = assistant.client.beta.threads.messages.list(thread_id=my_thread.id)
        print("__________________________________________________________________________________")
        for thread_message in messages.data:
            # Iterate over the 'content' attribute of the ThreadMessage, which is a list
            for content_item in thread_message.content:
                # Assuming content_item is a MessageContentText object with a 'text' attribute
                # and that 'text' has a 'value' attribute, print it
                print(content_item.text.value)
        print("__________________________________________________________________________________")
        break
    else:
        print("Run is in progress - Please Wait")
    continue





