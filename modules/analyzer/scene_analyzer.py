import json
import requests
import re
import time
import os

class OllamaDirector:
    def __init__(self, model="llama3", host="http://localhost:11434"):
        self.model = model
        self.host = host
        self.api_url = f"{host}/api/generate"

    def clean_json_string(self, json_str):
        """
        Limpa a resposta do LLM para extrair apenas o JSON válido.
        """
        json_str = re.sub(r'```json\s*', '', json_str)
        json_str = re.sub(r'```\s*$', '', json_str)
        
        match = re.search(r'\{.*\}', json_str, re.DOTALL)
        if match:
            return match.group(0)
        return json_str

    def analyze_scene(self, scene_text, scene_id_label):
        """
        Envia o bloco da cena para o Ollama e converte em Roteiro.
        """
        if not scene_text or len(scene_text.strip()) < 10:
            return None

        # --- PROMPT ENGINEERING AVANÇADO ---
        # Instruímos a IA a agir como Roteirista e Diretor Visual.
        # O Output deve ser estritamente o JSON solicitado.
        system_prompt = """
        Você é um Roteirista e Diretor Visual de IA experiente.
        Sua tarefa é converter um texto literário em um Script de Produção estruturado (JSON).
        
        INSTRUÇÕES DE ANÁLISE:
        1. Identifique o CENÁRIO VISUAL (apenas um, que represente a cena toda).
        2. Identifique o SOM AMBIENTE (SFX).
        3. Liste os PERSONAGENS presentes, com descrição visual breve e o que estão fazendo.
        4. Crie o SCRIPT sequencial, dividindo entre 'narration' (ação/descrição) e 'dialogue' (fala).
        
        FORMATO DE RESPOSTA (JSON APENAS):
        {
            "location_visual": "Descrição detalhada do ambiente para um artista desenhar (ex: Taverna escura, madeira podre, luz de velas)",
            "ambient_sound": "Sons de fundo (ex: chuva lá fora, copos batendo)",
            "characters_present": [
                {
                    "name": "Nome do Personagem",
                    "visual_desc": "Cabelo, roupa, traços marcantes",
                    "current_action": "O que ele faz na cena (ex: Bebendo no canto)"
                }
            ],
            "script": [
                {
                    "type": "narration",
                    "text": "Descrição da ação que ocorre."
                },
                {
                    "type": "dialogue",
                    "character": "Nome de quem fala",
                    "emotion": "Emoção da fala (ex: Raiva, Sussurro, Ironia)",
                    "text": "A fala exata do personagem."
                }
            ]
        }
        
        IMPORTANTE: Responda APENAS com o JSON. Não inclua introduções.
        """

        user_prompt = f"CENA ID: {scene_id_label}\nTEXTO DA CENA:\n{scene_text}"

        payload = {
            "model": self.model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": False,
            "format": "json", # Força modo JSON (Llama 3 nativo)
            "options": {
                "temperature": 0.2, # Baixa temperatura para ser mais fiel e menos criativo/alucinado
                "num_ctx": 4096     # Garante janela de contexto maior para cenas longas
            }
        }

        try:
            start_t = time.time()
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            
            result_raw = response.json()['response']
            cleaned_json = self.clean_json_string(result_raw)
            
            data = json.loads(cleaned_json)
            data["scene_id"] = scene_id_label
            
            return data

        except json.JSONDecodeError:
            print(f"⚠️  Erro de Parsing JSON na cena {scene_id_label}. Tentando recuperar...")
            # Aqui poderíamos implementar uma lógica de 'retry', mas por ora retornamos None
            return None
        except Exception as e:
            print(f"❌ Erro na API do Ollama: {e}")
            return None

class SceneAnalyzer:
    def __init__(self, input_file="book_structure.json", output_file="book_scenes.json"):
        self.input_file = input_file
        self.output_file = output_file
        self.director = OllamaDirector(model="llama3")

    def format_chapter_id(self, chapter_val, width=5):
        """
        Formata o capítulo com zeros à esquerda ignorando a pontuação na contagem.
        Ex: "1.1" -> d_count=2 -> precisa de 3 zeros -> "0001.1"
        """
        chapter_str = str(chapter_val)
        digit_count = len(re.sub(r'[^0-9]', '', chapter_str))
        needed_zeros = max(0, width - digit_count)
        return ("0" * needed_zeros) + chapter_str

    def run(self, limit_scenes=None):
        if not os.path.exists(self.input_file):
            print(f"❌ Arquivo {self.input_file} não encontrado. Rode o Módulo 01 primeiro.")
            return

        with open(self.input_file, 'r', encoding='utf-8') as f:
            book_data = json.load(f)

        print(f"🎬 Iniciando Roteirização de: {book_data.get('book_title', 'Livro')}")
        
        final_output = {
            "book_title": book_data.get("book_title"),
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "scenes_script": []
        }

        scene_counter = 0
        
        for chapter in book_data.get("chapters", []):
            chapter_num = self.format_chapter_id(chapter.get("chapter", "0"))
            chapter_title = chapter.get("title", "Capítulo")
            print(f"\n📂 {chapter_title} (ID: {chapter_num})...")

            for scene in chapter.get("scenes", []):
                original_text = scene.get("text")
                internal_id = scene.get("scene_id")
                
                # Cria um ID legível: cap00001.1_cena0000000001
                scene_label = f"cap{chapter_num}_cena{internal_id:010d}"
                
                print(f"   🎥 Processando {scene_label} ({len(original_text.split())} palavras)...", end=" ")
                script_data = self.director.analyze_scene(original_text, scene_label)
                
                if script_data:
                    final_output["scenes_script"].append(script_data)
                    print("✅ OK")
                    scene_counter += 1
                else:
                    print("❌ Falha")

                if limit_scenes and scene_counter >= limit_scenes:
                    print(f"\n🛑 Limite de teste atingido ({limit_scenes} cenas).")
                    break
            
            if limit_scenes and scene_counter >= limit_scenes:
                break

        if os.path.exists(self.output_file):
            try:
                os.remove(self.output_file)
            except: pass

        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, ensure_ascii=False, indent=4)

        print(f"\n💾 Roteiro salvo em: {self.output_file}")
        print(f"📊 Total de Cenas Roteirizadas: {len(final_output['scenes_script'])}")


# --- MAIN ---
if __name__ == "__main__":
    if os.path.exists("test_book_scenes.json"):
        try:
            os.remove("test_book_scenes.json")
            print(f"🗑️ Arquivo antigo removido: test_book_scenes.json")
        except OSError as e:
            print(f"⚠️ Aviso: Não foi possível remover o arquivo antigo. Erro: {e}")

    analyzer = SceneAnalyzer(input_file="test_book_structure.json", output_file="test_book_scenes.json")
    analyzer.run(limit_scenes=3)