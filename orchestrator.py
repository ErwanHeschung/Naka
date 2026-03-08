from ollama import Client
import json
from configs.config_manager import config

class AssistantOrchestrator:
    def __init__(self, registry):
        self.registry = registry
        self.config = config
        
        self.model_name = self.config.ai['model']['name']
        self.client = Client(host=self.config.infra['ollama']['host'])

    def _check_model_availability(self):
        """Returns True if the configured model exists in Ollama."""
        resp = self.client.list()
        
        models = [m.model if hasattr(m, 'model') else m.get('model', m.get('name')) 
                  for m in (resp.models if hasattr(resp, 'models') else resp.get('models', []))]
        return self.model_name in models

    def _build_system_prompt(self):
        """Merges personality and tool metadata into one prompt."""
        personality = self.config.ai['personality']
        name = self.config.ai['assistant']['name']
        tools = self.registry.get_tools_metadata()
        
        return (
            f"Role: {name}\n"
            f"Role: {personality['role']}\n"
            f"Style: {personality['style']}\n"
            f"Instructions: {personality['instructions']}\n"
            f"Tools: {json.dumps(tools)}"
        )

    def query(self, user_text: str):
        try:
            if not self._check_model_availability():
                return f"Error: Model {self.model_name} not found in Ollama."

            response = self.client.generate(
                model=self.model_name,
                system=self._build_system_prompt(),
                prompt=user_text,
                options={
                    "temperature": self.config.ai['model']['temperature'],
                    "num_predict": self.config.ai['model']['max_tokens']
                }
            )
            
            raw_output = getattr(response, 'response', response.get('response', ""))

            try:
                data = json.loads(raw_output.strip())
                if "function" in data:
                    return self.registry.dispatch(data['function'], data['params'])
            except json.JSONDecodeError:
                pass 
                
            return raw_output

        except Exception as e:
            return f"Orchestrator Error: {type(e).__name__} - {str(e)}"