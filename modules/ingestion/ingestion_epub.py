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
                
        # Controle de numeração
        self.last_chapter_num = 0
        self.sub_chapter_count = 0
        
        # Regex para identificar separadores visuais no texto (ex: ***, * * *, ---)
        self.separator_pattern = re.compile(r'^[\s\*\-\_\~•]{3,}$')
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        self.html_garbage_pattern = re.compile(r'(html public|w3c|dtd xhtml|xmlns|xml version|doctype|encoding=).*', re.IGNORECASE)
        self.number_extractor = re.compile(r'(\d+)')

    def load_book(self):
        try:
            print(f"📚 [EPUB] Lendo arquivo: {self.epub_path}...")
            self.book = epub.read_epub(self.epub_path)
            titles = self.book.get_metadata('DC', 'title')
            self.structure["book_title"] = titles[0][0] if titles else "Título Desconhecido"
        except Exception as e:
            print(f"❌ Erro ao ler EPUB: {e}")
            raise

    def get_next_chapter_number(self, title):
        """
        Lógica de numeração incremental e inteligente.
        Caso exista valor irá receber o mesmo do capítulo.
        Caso não exista valor irá receber um incremental de capítulo: 1, 2, 3...
        Caso exista valor anterior, mas o capitulo não tem, irá receber subnivel: 3.1, 3.2, 3.3...
        """
        match = self.number_extractor.search(title)
        
        if match:
            num_found = int(match.group(1))
            self.last_chapter_num = num_found
            self.sub_chapter_count = 0
            return str(num_found)
        else:
            if self.last_chapter_num == 0:
                self.last_chapter_num = 1
                return "1"
            else:
                self.sub_chapter_count += 1
                return f"{self.last_chapter_num}.{self.sub_chapter_count}"    

    def clean_text(self, text):
        if not text: 
            return ""
        text = self.url_pattern.sub('', text)
        text = self.html_garbage_pattern.sub('', text)
        clean = " ".join(text.split()).strip()
        if clean.lower() in ["", "html", "xml", "content-type"]:
            return ""
        return clean

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

        chapter_num_label = self.get_next_chapter_number(chapter_title)
        scenes = []
        current_scene_text = []

        # Itera sobre todos os elementos filhos do body para manter a ordem
        # Se não tiver body, pega tudo
        root = soup.body if soup.body else soup

        for element in root.find_all(['p', 'div', 'hr', 'h1', 'h2', 'h3']):
            if element.name == 'hr':
                if current_scene_text:
                    full_text = " ".join(current_scene_text).strip()
                    if full_text: scenes.append(full_text)
                    current_scene_text = []
                continue

            raw_text = element.get_text(strip=True)
            clean_content = self.clean_text(raw_text)

            if not clean_content:
                continue

            if self.separator_pattern.match(clean_content):
                if current_scene_text:
                    full_text = " ".join(current_scene_text).strip()
                    if full_text: scenes.append(full_text)
                    current_scene_text = []
            else:
                if len(clean_content) > 2 and not clean_content.startswith(("{", "var ", "/*", "function(")):
                    current_scene_text.append(clean_content)

        if current_scene_text:
            full_text = " ".join(current_scene_text).strip()
            if full_text: scenes.append(full_text)

        final_scenes = []
        for scene_text in scenes:
            if scene_text.lower() == chapter_title.lower():
                continue
                
            chunks = self.split_large_text(scene_text, max_words=1500)
            for chunk in chunks:
                if chunk.strip():
                    final_scenes.append({
                        "scene_id": len(final_scenes) + 1,
                        "text": chunk
                    })

        if final_scenes:
            return {
                "title": chapter_title,
                "chapter": chapter_num_label,
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