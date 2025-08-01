import json, os
import boto3
import asyncio
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

class ModelStreamer:
    def __init__(self, config_path="/home/ec2-user/chatbot/config/model_config.json", region="us-east-1"):
        self.bedrock = boto3.client(service_name="bedrock-runtime", region_name=region)
        self.region = region
        
        # Models that don't support system messages
        self.no_system_message_models = {
            # Titan models - none support system messages
            "amazon.titan-text-lite-v1",
            "amazon.titan-text-express-v1",
            "amazon.titan-text-premier-v1",
        }
        
        # Models that DO support system messages
        self.system_message_models = {
            # Nova models - test both with and without version suffixes
            "amazon.nova-lite-v1",
            "amazon.nova-pro-v1", 
            "amazon.nova-premier-v1",
            "amazon.nova-lite-v1:0",
            "amazon.nova-pro-v1:0",
            "amazon.nova-premier-v1:0",
        }
        
        self.model_map = self.load_model_config(config_path)
        print(f"Loaded {len(self.model_map)} models:")
        for name, config in self.model_map.items():
            print(f"  - {name}: {config['id']}")

    def load_model_config(self, path):
        try:
            current_dir = os.getcwd()
            full_path = os.path.abspath(path)
            print(f"Current directory: {current_dir}")
            print(f"Looking for config at: {full_path}")
            
            if not os.path.exists(path):
                print(f"Config file not found at: {path}")
                print("Using default model configuration")
                return {
                    "Nova Pro": {
                        "id": "amazon.nova-pro-v1:0",  # Try with version suffix first
                        "key": "nova-pro",
                        "provider": "Amazon",
                        "type": "text",
                        "quality": "high"
                    },
                    "Nova Premier": {
                        "id": "amazon.nova-premier-v1:0",  # Try with version suffix first
                        "key": "nova-premier",
                        "provider": "Amazon",
                        "type": "text",
                        "quality": "enterprise"
                    },
                    "Nova Lite": {
                        "id": "amazon.nova-lite-v1:0",  # Try with version suffix first
                        "key": "nova-lite",
                        "provider": "Amazon",
                        "type": "text",
                        "quality": "basic"
                    },
                    "Titan Premier": {
                        "id": "amazon.titan-text-premier-v1:0",  # Try with version suffix
                        "key": "titan-premier",
                        "provider": "Amazon",
                        "type": "text",
                        "quality": "high"
                    },
                    "Titan Lite": {
                        "id": "amazon.titan-text-lite-v1",
                        "key": "titan-lite",
                        "provider": "Amazon",
                        "type": "text",
                        "quality": "low"
                    },
                    "Titan Express": {
                        "id": "amazon.titan-text-express-v1",
                        "key": "titan-express",
                        "provider": "Amazon",
                        "type": "text",
                        "quality": "medium"
                    }
                }
            
            with open(path, "r") as f:
                config = json.load(f)
                print(f"Successfully loaded config with {len(config)} models")
                return config
                
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in config file: {e}")
            raise
        except Exception as e:
            print(f"Error loading model config: {e}")
            raise

    def model_supports_system_messages(self, model_id):
        """Check if the model supports system messages"""
        print(f"Checking system message support for: {model_id}")
        
        # Check exact matches first
        if model_id in self.system_message_models:
            print(f"  ✓ {model_id} explicitly supports system messages")
            return True
        if model_id in self.no_system_message_models:
            print(f"  ✗ {model_id} explicitly does NOT support system messages")
            return False
            
        # Check by pattern for Nova models
        if "nova" in model_id.lower():
            print(f"  ✓ {model_id} is Nova model - assuming system message support")
            return True
        # Check by pattern for Titan models  
        if "titan" in model_id.lower():
            print(f"  ✗ {model_id} is Titan model - assuming NO system message support")
            return False
            
        # Default assume support
        print(f"  ? {model_id} unknown - assuming system message support")
        return True
        
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

    def build_messages_with_system(self, system_message, chat_history):
        """Build messages for models that support system messages (like Nova)"""
        try:
            messages = []
            if system_message:
                messages.append(system_message)
            messages.extend(chat_history)
            print(f"Built {len(messages)} messages WITH system support")
            return messages
        except Exception as e:
            print(f"Error building messages with system support: {e}")
            return chat_history

    def build_messages_without_system(self, system_message, chat_history):
        """Build messages for models that don't support system messages (like Titan)"""
        try:
            messages = []
            system_content = system_message.content if system_message else None
            
            if system_content and chat_history:
                first_message = chat_history[0]
                if isinstance(first_message, HumanMessage):
                    combined_content = f"{system_content}\n\nUser: {first_message.content}"
                    messages.append(HumanMessage(content=combined_content))
                    messages.extend(chat_history[1:])
                else:
                    messages.append(HumanMessage(content=system_content))
                    messages.extend(chat_history)
            elif system_content:
                messages.append(HumanMessage(content=system_content))
            else:
                messages = chat_history
                
            print(f"Built {len(messages)} messages WITHOUT system support")
            return messages
        except Exception as e:
            print(f"Error building messages without system support: {e}")
            return chat_history or []

    async def invoke_model_streaming(self, model_id, messages, temperature):
        try:
            print(f"\n🚀 INVOKING MODEL: {model_id}")
            print(f"   Temperature: {temperature}")
            print(f"   Messages count: {len(messages)}")
            
            # Print message details for debugging
            for i, msg in enumerate(messages):
                msg_type = type(msg).__name__
                content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                print(f"   Message {i}: {msg_type} - {content_preview}")
            
            llm = ChatBedrockConverse(
                model_id=model_id,
                region_name=self.region,
                temperature=temperature
            )
            
            chunk_count = 0
            for chunk in llm.stream(messages):
                chunk_count += 1
                if hasattr(chunk, 'content') and chunk.content:
                    for content_item in chunk.content:
                        if isinstance(content_item, dict) and content_item.get('type') == 'text':
                            text = content_item.get('text', '')
                            if text:
                                yield text
                        elif hasattr(content_item, 'text'):
                            # Handle different chunk formats
                            yield content_item.text
                elif hasattr(chunk, 'content') and isinstance(chunk.content, str):
                    # Handle direct string content
                    yield chunk.content
            
            print(f"   ✓ Model {model_id} completed with {chunk_count} chunks")
            
        except Exception as e:
            print(f"   ❌ ERROR with model {model_id}: {str(e)}")
            print(f"   Error type: {type(e).__name__}")
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
        print(f"\n=== STREAMING {len(selected_models)} MODELS ===")
        print(f"Models: {selected_models}")
        print(f"System prompt: {system_prompt[:100] if system_prompt else 'None'}...")
        print(f"Chat history length: {len(chat_history)}")
        
        selected_model_keys = [self.model_map[name]["key"] for name in selected_models]
        history_by_model = self.get_history_per_model(chat_history, selected_model_keys)

        active_gens = {}
        for model_name in selected_models:
            print(f"\n--- Processing {model_name} ---")
            model_info = self.model_map[model_name]
            key = model_info["key"]
            model_id = model_info["id"]
            history = history_by_model[key]["messages"]
            system_message = history_by_model[key]["system_message"]
            
            if not system_message and system_prompt:
                system_message = SystemMessage(content=system_prompt)
            
            print(f"Model ID: {model_id}")
            print(f"History length: {len(history)}")
            print(f"System message: {'Yes' if system_message else 'No'}")
            
            # Choose appropriate message building based on model capabilities
            if self.model_supports_system_messages(model_id):
                messages = self.build_messages_with_system(system_message, history)
            else:
                messages = self.build_messages_without_system(system_message, history)
            
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
                    print(f"✓ {model_name} finished with {len(responses[model_name])} characters")
                    del tasks[model_name]
                except Exception as e:
                    print(f"❌ Error with {model_name}: {e}")
                    placeholders[model_name].markdown(f"Error: {str(e)}")
                    del tasks[model_name]

        return responses