import os
import json
import argparse
from pathlib import Path
from analyzer_epub import EpubIngestor

class ContentAnalyzer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.extension = Path(file_path).suffix.lower()

    def process(self):
        """
        Identifica a extensão e chama o processador adequado.
        """
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"O arquivo '{self.file_path}' não foi encontrado.")

        match self.extension:
            case '.epub':
                print(f"🔍 Detectado formato EPUB. Iniciando ingestão...")
                ingestor = EpubIngestor(self.file_path)
                return ingestor.run()
            
            # Futuras implementações:
            # case '.pdf':
            #     return PdfIngestor(self.file_path).run()
            # case '.txt':
            #     return TextIngestor(self.file_path).run()
            
            case _:
                error_msg = f"❌ Formato não suportado: '{self.extension}'. Apenas .epub é aceito no momento."
                raise ValueError(error_msg)

    def save_json(self, data, output_path="book_structure.json"):
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"💾 JSON estruturado salvo em: {output_path}")

# --- MAIN GERAL ---
if __name__ == "__main__":    
    ARQUIVO_ALVO = "exemplo.epub"

    try:
        analyzer = ContentAnalyzer(ARQUIVO_ALVO)
        book_data = analyzer.process()
        analyzer.save_json(book_data)
        
    except ValueError as ve:
        print(ve)
    except FileNotFoundError as fnf:
        print(f"❌ Erro Crítico: {fnf}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")