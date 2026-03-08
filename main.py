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
        user_input = ears.listen() 
        
        if user_input:
            sentence_buffer = ""
            for chunk in assistant.query(user_input):
                token = chunk.get('response', '')
                sentence_buffer += token
                
                if any(punct in token for punct in [".", "!", "?", "\n"]):
                    if sentence_buffer.strip():
                        voice.speak(sentence_buffer.strip())
                        sentence_buffer = ""

if __name__ == "__main__":
    main()