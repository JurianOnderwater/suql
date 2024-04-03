from openai import OpenAI
from typing_extensions import override
from time import sleep


class Assistant:
    def __init__(self, asst_id: str) -> None:
        self.instructions = """
                            You are a restaurant virtual assistant chatting with a user.
You can access a restaurant dataset (json file) to retrieve information about restaurants and their reviews. You may incorporate information from user reviews or your own general knowledge in your replies, but DO NOT make up facts about restaurants. Do not repeat yourself. You cannot propose reservations.

In your response, first accurately tell the user what query you have searched for (if you have searched for anything), then tell the user the result.

If you did not check the json file, even though the user made a restaurant request, you should tell the user that you couldn't help them with that request.

The number of returned results might not match exactly what you have searched for. In this case, do not make up additional restaurants and only report returned results.

The provided json file is a list containing data about restaurants. Each entry contains the following fields:
    "Name", "Location", "Price", "Open", "Rating", "Reviews"
"""
        self.client = OpenAI()
        if asst_id != None:
            self.assistant = self.client.beta.assistants.retrieve(asst_id)
            self.assistant = self.client.beta.assistants.update(
                asst_id, instructions=self.instructions,
                model="gpt-3.5-turbo", tools=[{'type': 'code_interpreter'}]
            )
        else:
            self.assistant = self.client.beta.assistants.create(
                instructions=self.instructions,
                name="Restaurant Expert",
                tools=[{"type": "code_interpreter"}, {"type": "retrieval"}],
                model="gpt-3.5-turbo",
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
        file__ = self.client.files.create(file=open(file, "rb"), purpose="assistants")
        self.assistant_file = self.client.beta.assistants.files.create(
            assistant_id=self.assistant.id, file_id=file__.id
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
                role="user",
                content=prompt,
            )

    def run(self):
        self.run = self.client.beta.threads.runs.create(
            thread_id=self.thread.id, assistant_id=self.assistant.id
        )


assistant = Assistant(asst_id="asst_JwP2UdeXqgPqrt2x9G9YqxxB")
assistant.use_file(file="/Users/jurianonderwater/Downloads/structured.json")
# assistant.use_prompts(prompts=["Which different restaurants can be considered 'cost effective', or 'cheap', based on the reviews. Search until you find 5"])
with open("prompts/prompts.txt", "r") as prompts_file:
    assistant.use_prompts(prompts=prompts_file.readlines())
print(
    "Starting run ...\n__________________________________________________________________________________"
)
assistant.run()
while True:
    sleep(3)
    my_thread = assistant.client.beta.threads.retrieve(assistant.thread.id)
    run_status = assistant.client.beta.threads.runs.retrieve(
        thread_id=assistant.thread.id, run_id=assistant.run.id
    )
    if run_status.status == "completed":
        print("Run is Completed")
        messages = assistant.client.beta.threads.messages.list(thread_id=my_thread.id)
        print(
            "__________________________________________________________________________________"
        )
        for thread_message in messages.data:
            # Iterate over the 'content' attribute of the ThreadMessage, which is a list
            for content_item in thread_message.content:
                # Assuming content_item is a MessageContentText object with a 'text' attribute
                # and that 'text' has a 'value' attribute, print it
                print(content_item.text.value)
        print(
            "__________________________________________________________________________________"
        )
        break
    else:
        print("Run is in progress - Please Wait")
    continue
