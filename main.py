from registry import CommandRegistry
from orchestrator import AssistantOrchestrator
from commands.light_control import LightControl
from commands.system_info import SystemInfo
from utils.logger import log
from configs.config_manager import config
from engines.voice_engine import VoiceEngine
from engines.ear_engine import EarEngine

def main():
    log.info(f"Starting {config.ai['assistant']['name']}")
    log.info(f"Ollama Target: {config.infra['ollama']['host']}")
    
    voice = VoiceEngine()
    ears = EarEngine()
    
    reg = CommandRegistry()
    reg.register(LightControl())
    reg.register(SystemInfo())
    
    assistant = AssistantOrchestrator(reg)

    while True:
        user_text = ears.listen()
        
        if user_text:
            log.debug(f"You said: {user_text}")
            
            if "exit" in user_text.lower():
                voice.speak("Goodbye!")
                break
            
            response = assistant.query(user_text)
            
            print(f"Assistant: {response}")
            voice.speak(response)

if __name__ == "__main__":
    main()