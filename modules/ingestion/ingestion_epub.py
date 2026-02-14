import json
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import warnings
import os

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
        if text:
            return " ".join(text.split())
        return ""

    def process_item_content(self, item):
        """Extrai texto de um item (capítulo) do EPUB."""
        soup = BeautifulSoup(item.get_content(), 'html.parser')

        # Busca título do capítulo
        chapter_title = ""
        header_tag = soup.find(['h1', 'h2', 'h3'])
        if header_tag:
            chapter_title = self.clean_text(header_tag.get_text())

        paragraphs = []
        for p in soup.find_all('p'):
            text = self.clean_text(p.get_text())
            # Filtra parágrafos muito curtos (ruído)
            if len(text) > 2: 
                paragraphs.append({
                    "text": text
                })

        if paragraphs:
            return {
                "title": chapter_title,
                "paragraphs": paragraphs
            }
        return None

    def run(self):
        self.load_book()
        print("📖 Processando capítulos na ordem de leitura (Spine)...")
        
        for item_ref in self.book.spine:
            item_id = item_ref[0]
            item = self.book.get_item_with_id(item_id)

            if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
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