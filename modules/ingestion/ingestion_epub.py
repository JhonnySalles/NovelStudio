import json
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, NavigableString, Tag
import warnings
import os
import re

warnings.filterwarnings('ignore')

class EpubIngestor:
    def __init__(self, epub_path):
        self.epub_path = epub_path
        self.book = None
        self.structure = {
            "source_file": os.path.basename(epub_path),
            "book_title": "",
            "chapters": []
        }
        
        # Regex para identificar separadores visuais no texto (ex: ***, * * *, ---)
        self.separator_pattern = re.compile(r'^[\s\*\-\_\~•]{3,}$')
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

    def load_book(self):
        try:
            print(f"📚 [EPUB] Lendo arquivo: {self.epub_path}...")
            self.book = epub.read_epub(self.epub_path)
            titles = self.book.get_metadata('DC', 'title')
            self.structure["book_title"] = titles[0][0] if titles else "Título Desconhecido"
        except Exception as e:
            print(f"❌ Erro ao ler EPUB: {e}")
            raise

    def clean_text(self, text):
        if not text: return ""
        text = self.url_pattern.sub('', text)
        return " ".join(text.split())

    def split_large_text(self, text, max_words=1500):
        """
        Divide um texto gigante em blocos menores respeitando final de frases.
        """
        words = text.split()
        if len(words) <= max_words:
            return [text]

        chunks = []
        current_chunk = []
        current_count = 0

        sentences = re.split(r'(?<=[.!?]) +', text)
        
        for sentence in sentences:
            sentence_word_count = len(sentence.split())
            
            if current_count + sentence_word_count > max_words:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_count = sentence_word_count
            else:
                current_chunk.append(sentence)
                current_count += sentence_word_count
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return chunks

    def process_item_content(self, item, chapter_id):
        """
        Extrai cenas baseadas em separadores visuais ou tags <hr>.
        """
        soup = BeautifulSoup(item.get_content(), 'html.parser')

        # Tenta achar título
        chapter_title = f"Capítulo {chapter_id}"
        header_tag = soup.find(['h1', 'h2', 'h3'])
        if header_tag:
            chapter_title = self.clean_text(header_tag.get_text())

        scenes = []
        current_scene_text = []

        # Itera sobre todos os elementos filhos do body para manter a ordem
        # Se não tiver body, pega tudo
        root = soup.body if soup.body else soup

        for element in root.descendants:
            if isinstance(element, NavigableString) and element.parent.name not in ['p', 'div', 'span']:
                continue

            if isinstance(element, Tag):
                if element.name == 'hr':
                    if current_scene_text:
                        scenes.append(" ".join(current_scene_text))
                        current_scene_text = []
                    continue
                
                if element.name not in ['p', 'div']:
                    continue

                raw_text = element.get_text(strip=True)
                clean_content = self.clean_text(raw_text)

                if not clean_content:
                    continue

                if self.separator_pattern.match(clean_content):
                    if current_scene_text:
                        scenes.append(" ".join(current_scene_text))
                        current_scene_text = []

                else:
                    if len(clean_content) > 3 and not clean_content.startswith(("{", "var ", "/*")):
                        current_scene_text.append(clean_content)

        if current_scene_text:
            scenes.append(" ".join(current_scene_text))

        final_scenes = []
        for i, scene_text in enumerate(scenes):
            chunks = self.split_large_text(scene_text, max_words=1500)
            for chunk in chunks:
                final_scenes.append({
                    "scene_id": len(final_scenes) + 1,
                    "text": chunk
                })

        if final_scenes:
            return {
                "title": chapter_title,
                "scenes": final_scenes
            }
        return None

    def run(self):
        self.load_book()
        print("📖 Processando com Segmentação Inteligente de Cenas...")
        
        processed_ids = set()
        chap_counter = 0

        for item_ref in self.book.spine:
            item_id = item_ref[0]
            if item_id in processed_ids: continue
                
            item = self.book.get_item_with_id(item_id)

            if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                processed_ids.add(item_id)
                chap_counter += 1
                
                chapter_data = self.process_item_content(item, chap_counter)
                if chapter_data:
                    self.structure["chapters"].append(chapter_data)

        return self.structure


# --- MAIN DE TESTE ---
if __name__ == "__main__":
    ARQUIVO_TESTE = "exemplo.epub"
    if os.path.exists(ARQUIVO_TESTE):
        ingestor = EpubIngestor(ARQUIVO_TESTE)
        resultado = ingestor.run()

        if os.path.exists("test_book_structure.json"):
            try:
                os.remove("test_book_structure.json")
                print(f"🗑️ Arquivo antigo removido: test_book_structure.json")
            except OSError as e:
                print(f"⚠️ Aviso: Não foi possível remover o arquivo antigo. Erro: {e}")
        
        with open("test_book_structure.json", "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=4)
            
        print(f"✅ Processamento concluído: {resultado['book_title']}")
        total_cenas = sum(len(c['scenes']) for c in resultado['chapters'])
        print(f"🎬 Total de Cenas detectadas: {total_cenas}")
        
        # Debug: Mostrar tamanho da primeira cena
        if total_cenas > 0:
            primeira_cena = resultado['chapters'][0]['scenes'][0]['text']
            print(f"📝 Amostra da Cena 1 ({len(primeira_cena.split())} palavras):\n{primeira_cena[:200]}...")
    else:
        print("⚠️ Arquivo de teste não encontrado.")