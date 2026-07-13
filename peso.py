import os
import time
import traceback
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException

load_dotenv()
USUARIO = os.getenv('USUARIO_RFID')
SENHA = os.getenv('SENHA_RFID')

DIR = os.path.dirname(os.path.abspath(__file__))

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file(os.path.join(DIR, 'credenciais.json'), scopes=SCOPES)
gc = gspread.authorize(creds)
SHEET_ID = '1JXvEHzdD8nyrtA19b9MBKHe_0DCjfteaEuCQ_rrtIGw'
planilha = gc.open_by_key(SHEET_ID)
aba = planilha.worksheet('Peso_Bruto')

hoje = datetime.now()

dias_do_mes = list(range(1, hoje.day + 1))
# 🔒 TRAVA DE TESTE — descomente a linha abaixo para rodar só o dia 1 antes de soltar em produção total
# dias_do_mes = dias_do_mes[:1]


def parse_num(txt):
    """Converte número no padrão BR ('1.234,5' ou '1234,5') para float."""
    if not txt or not txt.strip():
        return 0.0
    limpo = txt.strip().replace('.', '').replace(',', '.')
    try:
        return float(limpo)
    except ValueError:
        return 0.0


def aceitar_alerta_se_houver(nav, timeout=3):
    """Espera ativamente por um alert em vez de sleep fixo; retorna rápido se não houver."""
    try:
        WebDriverWait(nav, timeout).until(EC.alert_is_present())
        nav.switch_to.alert.accept()
    except TimeoutException:
        pass


print(f"🤖 Iniciando o Robô de Peso — Foco: {hoje.strftime('%m/%Y')}")
print(f"📅 {len(dias_do_mes)} dia(s) do mês para processar (01 a {hoje.day:02d}).")

servico = Service(ChromeDriverManager().install())
navegador = webdriver.Chrome(service=servico)
navegador.set_page_load_timeout(120)

linhas_novas = []

try:
    print("🌐 Conectando ao servidor do Sistema São Geraldo...")
    conectou = False
    for t_login in range(1, 4):
        try:
            navegador.get("http://www.sistemasaogeraldo.com.br/hdk/saogeraldosystem/sistema/Login.aspx")
            conectou = True
            break
        except:
            print(f"  ⚠️ O site demorou a responder (Tentativa {t_login}/3). Tentando de novo em 5s...")
            time.sleep(5)

    if not conectou:
        raise Exception("O site do São Geraldo está fora do ar ou sua internet caiu.")

    navegador.maximize_window()
    print("🔐 Fazendo login...")

    espera = WebDriverWait(navegador, 30)
    espera.until(EC.presence_of_element_located((By.ID, "txtUsuario"))).send_keys(USUARIO)
    navegador.find_element(By.ID, "txtSenha").send_keys(SENHA)
    navegador.find_element(By.ID, "Button1").click()
    # Espera condicional: o combo só existe depois que o login processa o postback
    espera.until(EC.presence_of_element_located((By.NAME, "ctl00$ComboUnidade")))

    url_home_padrao = navegador.current_url.split('?')[0]
    url_diretorio_base = url_home_padrao.rsplit('/', 1)[0]

    print("🎯 Garantindo unidade TODAS selecionada...")
    select_el = espera.until(EC.presence_of_element_located((By.NAME, "ctl00$ComboUnidade")))
    navegador.execute_script("arguments[0].style.display = 'block';", select_el)
    Select(select_el).select_by_visible_text("TODAS")

    for dia in dias_do_mes:
        data_str = f"{dia:02d}/{hoje.month:02d}/{hoje.year}"
        print(f"\n📆 Processando dia {data_str}...")

        try:
            url_dia = f"{url_diretorio_base}/ListagemLavanderia.aspx?dia={data_str}"
            navegador.get(url_dia)
            aceitar_alerta_se_houver(navegador)

            tabela = espera.until(EC.presence_of_element_located((By.ID, "tabpedidos")))
            linhas = tabela.find_elements(By.TAG_NAME, "tr")

            count_dia = 0
            for linha in linhas[1:]:
                cols = linha.find_elements(By.TAG_NAME, "td")
                if len(cols) < 8:
                    continue
                nome_cliente = cols[0].text.strip()
                if not nome_cliente or nome_cliente.upper() == "TOTAL":
                    continue

                peso_sujo = parse_num(cols[1].text)
                peso_limpo = parse_num(cols[2].text)
                peso_relave = parse_num(cols[7].text)

                linhas_novas.append([
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    nome_cliente,
                    data_str,
                    peso_limpo,
                    peso_sujo,
                    peso_relave
                ])
                count_dia += 1

            print(f"  ✅ {count_dia} cliente(s) capturado(s).")

        except TimeoutException:
            print(f"  ⚠️ Tabela não carregou para o dia {data_str}. Pulando.")
        except Exception as e:
            print(f"  ⚠️ Erro no dia {data_str}: {e}")
            traceback.print_exc()

    if linhas_novas:
        print(f"\n💾 Gravando {len(linhas_novas)} linha(s) na aba Peso_Bruto...")
        aba.append_rows(linhas_novas, value_input_option='RAW')
        print("✅ Gravação concluída.")
    else:
        print("\n⚠️ Nenhuma linha capturada nesta rodada.")

except Exception as e:
    print(f"\n❌ Erro Fatal:")
    traceback.print_exc()
finally:
    navegador.quit()
    print("\n🛑 Robô de Peso finalizado!")
