import json, os
import boto3
import asyncio
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

class ModelStreamer:
    def __init__(self, config_path="config/model_config.json", region="ap-south-1"):
        self.bedrock = boto3.client(service_name="bedrock-runtime", region_name=region)
        self.region = region
        self.model_map = self.load_model_config(config_path)

    def load_model_config(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model config file not found at {path}")
        with open(path, "r") as f:
            return json.load(f)
        
    def get_history_per_model(self, chat_history, selected_model_keys):
        model_histories = {key: [] for key in selected_model_keys}
        system_message = None

        for message in chat_history:
            role = message.get("role")
            content = message.get("content")
            responses = message.get("responses", {})

            if role == "system":
                system_message = SystemMessage(content=content)

            elif role == "user":
                human_msg = HumanMessage(content=content)
                for key in selected_model_keys:
                    model_histories[key].append(human_msg)

            elif role == "assistant":
                for key in selected_model_keys:
                    if key in responses:
                        ai_msg = AIMessage(content=responses[key])
                        model_histories[key].append(ai_msg)

        return {
            key: {
                "system_message": system_message,
                "messages": model_histories[key]
            }
            for key in selected_model_keys
        }

    def build_prompt(self, system_message, chat_history):
        try:
            template = ChatPromptTemplate([
                ("system", system_message),
                ("placeholder", "{conversation}"),
                MessagesPlaceholder(variable_name="conversation", optional=True)
            ])
            return template.invoke({"conversation": chat_history}).to_messages()
        except Exception as e:
            print(f"Error creating prompt template: {e}")
            return None

    async def invoke_model_streaming(self, model_id, prompt_value, temperature):
        try:
            # Construct Titan-style payload
            input_text = ""
            for msg in prompt_value:
                if isinstance(msg, HumanMessage):
                    input_text += f"User: {msg.content}\n"
                elif isinstance(msg, AIMessage):
                    input_text += f"Assistant: {msg.content}\n"
                elif isinstance(msg, SystemMessage):
                    input_text += f"{msg.content}\n"
            payload = {
                "inputText": input_text,
                "textGenerationConfig": {
                    "temperature": temperature,
                    "maxTokenCount": 512,
                    "topP": 0.9,
                    "stopSequences": ["\nUser:"]
                }
            }

            response = self.bedrock.invoke_model(
                body=json.dumps(payload),
                modelId=model_id,
                accept="application/json",
                contentType="application/json"
            )

            result = json.loads(response['body'].read())
            output_text = result.get("results", [{}])[0].get("outputText", "")
            yield output_text

        except Exception as e:
            print(f"Error invoking model: {e}")
            import traceback
            traceback.print_exc()

    async def stream_models(
        self,
        selected_models,
        system_prompt,
        chat_history,
        temperature,
        placeholders
    ):
        selected_model_keys = [self.model_map[name]["key"] for name in selected_models]
        history_by_model = self.get_history_per_model(chat_history, selected_model_keys)

        active_gens = {}
        for model_name in selected_models:
            model_info = self.model_map[model_name]
            key = model_info["key"]
            model_id = model_info["id"]
            history = history_by_model[key]["messages"]
            print('➡ history:', history)
            prompt = self.build_prompt(system_prompt, history)
            gen = self.invoke_model_streaming(model_id, prompt, temperature)
            active_gens[model_name] = gen

        responses = {model_name: "" for model_name in selected_models}
        tasks = {
            model_name: asyncio.create_task(gen.__anext__())
            for model_name, gen in active_gens.items()
        }

        while tasks:
            done, _ = await asyncio.wait(tasks.values(), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                model_name = next(name for name, tsk in tasks.items() if tsk == task)
                try:
                    chunk = await task
                    responses[model_name] += chunk
                    placeholders[model_name].markdown(responses[model_name] + "▌")
                    tasks[model_name] = asyncio.create_task(active_gens[model_name].__anext__())
                except StopAsyncIteration:
                    placeholders[model_name].markdown(responses[model_name])
                    del tasks[model_name]
                except Exception as e:
                    print(f"Error with {model_name}: {e}")
                    del tasks[model_name]

        return responses

