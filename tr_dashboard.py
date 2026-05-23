from config import PYTR_PATH as PYTR, JSON_FILE, COOKIE_FILE, DOCS_PATH

import json
import os
import re
import subprocess
import yfinance as yf
from colorama import Fore, Style, init
init(autoreset=True)

# ===== LOGIN E AGGIORNAMENTO DATI =====
if os.path.exists(COOKIE_FILE):
    os.remove(COOKIE_FILE)

subprocess.run([PYTR, "login"])
subprocess.run([PYTR, "dl_docs", DOCS_PATH])

# ===== LETTURA JSON =====
with open(JSON_FILE, "r", encoding="utf-8") as f:
    events = json.load(f)

acquisti_etf = []
depositi = []
interessi = []

ETF_TYPES = {"SAVINGS_PLAN_INVOICE_CREATED", "TRADING_SAVINGSPLAN_EXECUTED"}
DEPOSITO_TYPES = {"PAYMENT_INBOUND", "PAYMENT_INBOUND_APPLE_PAY", "BANK_TRANSACTION_INCOMING"}

quote_totali = 0

for event in events:
    titolo = event.get("title") or ""
    sottotitolo = event.get("subtitle") or ""
    data = (event.get("timestamp") or "")[:10]
    event_type = event.get("eventType") or ""
    amount = event.get("amount") or {}
    valore = abs(amount.get("value", 0) or 0)

    if event_type in ETF_TYPES:
        acquisti_etf.append({"data": data, "nome": titolo, "valore": valore})

        details = event.get("details") or {}
        for section in details.get("sections", []):
            # Formato vecchio: sezione "Transaktion" con riga "Anteile"
            if section.get("title") == "Transaktion":
                for row in section.get("data", []):
                    if row.get("title") == "Anteile":
                        testo = row["detail"]["text"].replace(",", ".")
                        try:
                            quote_totali += float(testo)
                        except:
                            pass

            # Formato nuovo: sezione "Übersicht" con riga "Transaktion"
            if section.get("title") == "Übersicht":
                for row in section.get("data", []):
                    if row.get("title") == "Transaktion":
                        testo = row["detail"].get("text", "")
                        if "×" in testo:
                            try:
                                quote = testo.split("×")[0].strip().replace(",", ".")
                                quote_totali += float(quote)
                            except:
                                pass

    elif event_type in DEPOSITO_TYPES:
        depositi.append({"data": data, "valore": valore})

    elif event_type == "INTEREST_PAYOUT":
        interessi.append({"data": data, "tasso": sottotitolo, "valore": valore})

# ===== SALDO CASH =====
saldo_cash = 0.0
try:
    result = subprocess.run([PYTR, "portfolio"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if "Cash EUR" in line:
            match = re.search(r"([\d]+[.,][\d]+)", line)
            if match:
                saldo_cash = float(match.group(1).replace(",", "."))
                break
except Exception as e:
    print(Fore.RED + f"[ERRORE] Durante il caricamento del saldo: {e}")

# ===== STAMPA ACQUISTI ETF =====
print("\n" + "="*55)
print("       📊  TRADE REPUBLIC — DASHBOARD")
print("="*55)

print(f"\n📈  ACQUISTI ETF")
print(f"{'Data':<12} {'Nome':<30} {'Importo':>10}")
print("-"*55)
totale_etf = 0
for a in sorted(acquisti_etf, key=lambda x: x["data"]):
    print(f"{a['data']:<12} {a['nome']:<30} {a['valore']:>9.2f} €")
    totale_etf += a["valore"]
print(f"{'TOTALE':<43} {totale_etf:>9.2f} €")

# ===== STAMPA DEPOSITI =====
print(f"\n💰  DEPOSITI")
print(f"{'Data':<12} {'Importo':>10}")
print("-"*25)
totale_dep = 0
for d in sorted(depositi, key=lambda x: x["data"]):
    print(f"{d['data']:<12} {d['valore']:>9.2f} €")
    totale_dep += d["valore"]
print(f"{'TOTALE':<12} {totale_dep:>9.2f} €")

# ===== STAMPA INTERESSI =====
print(f"\n🏦  INTERESSI")
print(f"{'Data':<12} {'Tasso':<15} {'Importo':>10}")
print("-"*40)
totale_int = 0
for i in sorted(interessi, key=lambda x: x["data"]):
    print(f"{i['data']:<12} {i['tasso']:<15} {i['valore']:>9.2f} €")
    totale_int += i["valore"]
print(f"{'TOTALE':<28} {totale_int:>9.2f} €")

# ===== PERFORMANCE ETF =====
print(f"\n📊  PERFORMANCE ETF")
print(Fore.CYAN + "="*55)
try:
    ticker = yf.Ticker("CSPX.L")
    prezzo_usd = ticker.fast_info["last_price"]
    eur_ticker = yf.Ticker("EURUSD=X")
    cambio = eur_ticker.fast_info["last_price"]
    prezzo_eur = prezzo_usd / cambio

    valore_attuale = quote_totali * prezzo_eur
    guadagno = valore_attuale - totale_etf
    guadagno_pct = (guadagno / totale_etf * 100) if totale_etf > 0 else 0
    segno = "+" if guadagno >= 0 else ""

    print(f"  • Quote totali          : {quote_totali:>10.6f}")
    print(f"  • Prezzo attuale        : {prezzo_eur:>10.2f} € (ritardo ~15min)")
    print(f"  • Valore attuale ETF    : {valore_attuale:>10.2f} €")
    print(f"  • Totale versato        : {totale_etf:>10.2f} €")
    print(f"\n          Guadagno: {segno}{guadagno:.2f} € ({segno}{guadagno_pct:.2f}%)")
except Exception as e:
    print(Fore.RED + f"[ERRORE] Recupero prezzo: {e}")
    valore_attuale = 0.0

# ===== RIEPILOGO PORTAFOGLIO =====
print(f"\n📊  PORTAFOGLIO")
print(Fore.GREEN + "="*55)
print(f"  💵  Saldo cash                 : {saldo_cash:>8.2f} €")
print(f"  📈  Totale investimenti (ETF)  : {valore_attuale:>8.2f} €")
print(f"  💰  Totale depositi            : {totale_dep:>8.2f} €")
print(f"  🏦  Totale interessi           : {totale_int:>8.2f} €")
print(f"  💼  Totale patrimonio          : {valore_attuale + totale_int + saldo_cash:>8.2f} €")
print(Fore.GREEN + "="*55)