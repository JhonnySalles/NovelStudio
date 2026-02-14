import json
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
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

        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        self.doctype_pattern = re.compile(r'html public|doctype|w3c|dtd', re.IGNORECASE)

    def load_book(self):
        """Carrega o arquivo EPUB na memória."""
        try:
            print(f"📚 [EPUB] Lendo arquivo: {self.epub_path}...")
            self.book = epub.read_epub(self.epub_path)
            titles = self.book.get_metadata('DC', 'title')
            self.structure["book_title"] = titles[0][0] if titles else "Título Desconhecido"
        except Exception as e:
            print(f"❌ Erro ao ler EPUB: {e}")
            raise

    def clean_text(self, text):
        """Remove espaços extras e normaliza o texto."""
        if not text:
            return ""

        text = self.url_pattern.sub('', text)
        text = " ".join(text.split())
        
        return text

    def is_valid_paragraph(self, text):
        """
        A 'Porteira': Decide se o texto é narrativa útil ou lixo técnico.
        Retorna True se for válido, False se deve ser descartado.
        """
        if len(text) < 3:
            return False
            
        if self.doctype_pattern.search(text):
            return False
            
        if text.replace('.', '').isdigit():
            return False

        if text.startswith(("{", "function", "var ", "/*")):
            return False

        return True    

    def process_item_content(self, item):
        """Extrai texto de um item (capítulo) do EPUB."""
        soup = BeautifulSoup(item.get_content(), 'html.parser')

        chapter_title = ""
        header_tag = soup.find(['h1', 'h2', 'h3', 'h4'])
        if header_tag:
            chapter_title = self.clean_text(header_tag.get_text())

        paragraphs = []
        
        for tag in soup.find_all(['p', 'div']):
            raw_text = tag.get_text(strip=True) 
            clean_content = self.clean_text(raw_text)

            if self.is_valid_paragraph(clean_content):
                paragraphs.append({
                    "text": clean_content
                })

        if paragraphs:
            if not chapter_title:
                chapter_title = "Capítulo / Seção" 
                
            return {
                "title": chapter_title,
                "paragraphs": paragraphs
            }
        return None

    def run(self):
        self.load_book()
        print("📖 Processando capítulos na ordem de leitura (Spine)...")
        
        processed_ids = set()
        for item_ref in self.book.spine:
            item_id = item_ref[0]
            if item_id in processed_ids:
                continue
                
            item = self.book.get_item_with_id(item_id)
            if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                processed_ids.add(item_id)
                chapter_data = self.process_item_content(item)
                if chapter_data:
                    self.structure["chapters"].append(chapter_data)

        return self.structure

# --- MAIN GERAL ---
if __name__ == "__main__":
    ARQUIVO_TESTE = "exemplo.epub"
    if os.path.exists(ARQUIVO_TESTE):
        ingestor = EpubIngestor(ARQUIVO_TESTE)
        resultado = ingestor.run()
        
        with open("teste_epub_output.json", "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=4)
        print(f"✅ Teste concluído. Título: {resultado['book_title']}")
        print(f"📊 Capítulos extraídos: {len(resultado['chapters'])}")
    else:
        print("⚠️ Arquivo de teste não encontrado.")