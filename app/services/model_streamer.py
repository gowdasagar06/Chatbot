import json, os
import boto3
import asyncio
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, AIMessage

class ModelStreamer:
    def __init__(self, config_path="config/model_config.json", region="us-east-1"):
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
        system_prompt_content = None

        for message in chat_history:
            role = message.get("role")
            content = message.get("content")
            responses = message.get("responses", {})

            if role == "system":
                # Store system content but don't create SystemMessage
                system_prompt_content = content

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
                "system_content": system_prompt_content,
                "messages": model_histories[key]
            }
            for key in selected_model_keys
        }

    def build_messages_for_titan(self, system_content, chat_history):
        """Build messages for Titan models (no system message support)"""
        try:
            messages = []
            
            if system_content and chat_history:
                # Get the first user message and combine with system prompt
                first_message = chat_history[0]
                if isinstance(first_message, HumanMessage):
                    # Combine system prompt with first user message
                    combined_content = f"{system_content}\n\nUser: {first_message.content}"
                    messages.append(HumanMessage(content=combined_content))
                    # Add the rest of the conversation
                    messages.extend(chat_history[1:])
                else:
                    # If no user message to combine with, add system as instruction
                    messages.append(HumanMessage(content=system_content))
                    messages.extend(chat_history)
            elif system_content:
                # Only system content, no chat history
                messages.append(HumanMessage(content=system_content))
            else:
                # No system content, just use chat history
                messages = chat_history
                
            return messages
        except Exception as e:
            print(f"Error building messages for Titan: {e}")
            return chat_history or []

    async def invoke_model_streaming(self, model_id, messages, temperature):
        try:
            llm = ChatBedrockConverse(
                model_id=model_id,
                region_name=self.region,
                temperature=temperature
            )

            print(f"➡ Invoking Titan model {model_id} with {len(messages)} messages")
            
            for chunk in llm.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    for content_item in chunk.content:
                        if isinstance(content_item, dict) and content_item.get('type') == 'text':
                            text = content_item.get('text', '')
                            if text:
                                yield text
        except Exception as e:
            print(f"Error invoking model {model_id}: {e}")
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
            system_content = history_by_model[key]["system_content"] or system_prompt
            
            print(f'➡ Processing {model_name} (ID: {model_id}) with history length: {len(history)}')
            
            # Build messages without system message support
            messages = self.build_messages_for_titan(system_content, history)
            
            gen = self.invoke_model_streaming(model_id, messages, temperature)
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
