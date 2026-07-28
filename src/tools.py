from pydub import AudioSegment

def dividir_texto_em_partes(texto, n):
    """
    Divide o texto em uma lista de n partes aproximadamente iguais.

    Args:
        texto (str): O texto a ser dividido.
        n (int): O número de partes em que o texto será dividido.

    Returns:
        list: Lista contendo o texto dividido em n partes.
    """
    # Remove espaços extras e quebra de linhas para garantir melhor divisão
    texto = texto.strip()

    # Calcula o tamanho aproximado de cada parte
    tamanho_parte = len(texto) // n

    # Divisões do texto
    partes = []

    # Ponto de início para a próxima parte
    inicio = 0

    for i in range(n):
        # Define o fim da parte, tentando não cortar palavras no meio
        fim = inicio + tamanho_parte

        # Ajusta o fim para não cortar uma palavra
        if fim < len(texto):
            while fim < len(texto) and texto[fim] not in [' ', '\n']:
                fim += 1

        # Adiciona a parte à lista
        partes.append(texto[inicio:fim].strip())

        # Atualiza o início para a próxima parte
        inicio = fim

    return partes

def combinar_arquivos_audio(arquivos, arquivo_saida):
    """
    Combina múltiplos arquivos de áudio MP3 em um único arquivo.

    Args:
        arquivos (list): Lista com os caminhos dos arquivos de áudio a serem combinados.
        arquivo_saida (str): Caminho do arquivo de áudio combinado a ser salvo.
    """
    # Inicializa um segmento de áudio vazio
    audio_final = AudioSegment.empty()

    # Itera pelos arquivos e adiciona ao áudio final
    for arquivo in arquivos:
        audio = AudioSegment.from_mp3(arquivo)
        audio_final += audio

    # Exporta o áudio combinado para um único arquivo
    audio_final.export(arquivo_saida, format="mp3")
    print(f"Arquivo combinado salvo em: {arquivo_saida}")
