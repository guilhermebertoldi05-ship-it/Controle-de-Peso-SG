import os
import gspread
import pandas as pd
from datetime import datetime
from google.oauth2.service_account import Credentials

print("📊 Iniciando o Refinador de Peso...")

DIR = os.path.dirname(os.path.abspath(__file__))

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file(os.path.join(DIR, 'credenciais.json'), scopes=SCOPES)
gc = gspread.authorize(creds)
SHEET_ID = '1JXvEHzdD8nyrtA19b9MBKHe_0DCjfteaEuCQ_rrtIGw'
planilha = gc.open_by_key(SHEET_ID)


def normalizar_numero(valor):
    s = str(valor).strip()
    if not s or s == '-':
        return 0.0
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def get_or_create_sheet(nome, rows=1000, cols=10):
    try:
        return planilha.worksheet(nome)
    except gspread.exceptions.WorksheetNotFound:
        sheet = planilha.add_worksheet(title=nome, rows=rows, cols=cols)
        print(f"✅ Aba {nome} criada.")
        return sheet


try:
    aba_brutos = planilha.worksheet('Peso_Bruto')
    dados = aba_brutos.get_all_values()

    if len(dados) < 2:
        print("❌ Erro: Aba Peso_Bruto está vazia. Rode o peso.py primeiro.")
        exit()

    df = pd.DataFrame(dados[1:], columns=dados[0])
    df['Data Extração'] = pd.to_datetime(df['Data Extração'], format='%d/%m/%Y %H:%M')

    for col in ['Peso Limpo (kg)', 'Peso Sujo (kg)', 'Peso Relave (kg)']:
        df[col] = df[col].apply(normalizar_numero)

    # O sistema legado às vezes lista a mesma unidade em mais de uma linha com o
    # nome idêntico (ex: "SPA CENTRO" aparece 4x, cada linha com peso próprio) — soma
    # essas linhas dentro da MESMA rodada antes de deduplicar entre rodadas diferentes.
    df = df.sort_values(by='Data Extração')
    df_somado = df.groupby(['Data Extração', 'Cliente', 'Data'], as_index=False).agg({
        'Peso Limpo (kg)': 'sum',
        'Peso Sujo (kg)': 'sum',
        'Peso Relave (kg)': 'sum'
    })

    # Mantém a extração mais recente por Cliente + Data (corrige valores retroativos)
    df_somado = df_somado.sort_values(by='Data Extração')
    df_refinado = df_somado.drop_duplicates(subset=['Cliente', 'Data'], keep='last').copy()
    df_refinado['Data_dt'] = pd.to_datetime(df_refinado['Data'], format='%d/%m/%Y')

    df_refinado['% Relave'] = df_refinado.apply(
        lambda r: round((r['Peso Relave (kg)'] / r['Peso Sujo (kg)']) * 100, 2) if r['Peso Sujo (kg)'] > 0 else 0.0,
        axis=1
    )
    df_refinado['Ano-Mês'] = df_refinado['Data_dt'].dt.strftime('%Y-%m')

    df_refinado = df_refinado.sort_values(by=['Cliente', 'Data_dt'])

    colunas_finais = ['Cliente', 'Ano-Mês', 'Data', 'Peso Limpo (kg)', 'Peso Sujo (kg)',
                       'Peso Relave (kg)', '% Relave']
    df_refinado = df_refinado[colunas_finais]

    aba_refinado = get_or_create_sheet('Peso_Refinado')
    aba_refinado.clear()
    aba_refinado.update([df_refinado.columns.tolist()] + df_refinado.astype(str).values.tolist(),
                         value_input_option='RAW')

    print(f"✅ Sucesso! Peso_Refinado gerada com {len(df_refinado)} registros únicos (Cliente + Data).")

except Exception as e:
    print(f"❌ Erro ao refinar os dados: {e}")
