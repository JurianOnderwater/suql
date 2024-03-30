from openai import OpenAI

client = OpenAI()
# some_database = None 


class Assistant:
    def __init__(self) -> None:
        pass
        self.assistant = client.beta.assistants.create(
            instructions= """
                            You are a personal restaurant expert. When asked a 
                            question, check the provided csv file to answer the question.
                          """,
            name="Restaurant Expert",
            tools=[{"type": "code_interpreter"}],
            model="gpt-3.5-turbo",
            file_ids=[]
            #ID=asst_6zxjQbSHIc3hIcTEsyxRawDM
        )
        self.thread = client.beta.threads.create()

    def use_file(self, file: str):
        """
        Attatch file to assistant

        Args:
            file (str): path to the file
        """
        self.assistant_file =   client.beta.assistants.files.create(
                                assistant_id="asst_6zxjQbSHIc3hIcTEsyxRawDM",
                                file_id=file
                                )
    
    def use_prompts(self, prompts: list):
        """
        Add all the prompts to the thread as messages.

        Args:
            prompts (list): A list of strings containing all the prompts
        """
        for prompt in prompts:
            client.beta.threads.messages.create(
                self.thread.id,
                role="user",
                content=prompt,
                file_ids=[self.assistant_file.id]
                )
            
    def run(self):
        run = client.beta.threads.runs.create(
            thread_id=self.thread.id,
            assistant_id=self.assistant.id
            )



assistant = Assistant().assistant
print(assistant)


# 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
