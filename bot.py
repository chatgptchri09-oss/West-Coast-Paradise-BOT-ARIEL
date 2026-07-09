import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web
import asyncio
import os
import sys

sys.stdout.reconfigure(line_buffering=True)

import database
import backup
from constants import (
    STAFF_ROLE_ID, SCERIFFO_ROLE_ID, DOTTORE_ROLE_ID, ARMIERE_ROLE_ID,
    STALLA_ROLE_ID, SALOON_ROLE_ID, EMPORIO_ROLE_ID, CONTRABBANDO_ID,
    STATO_ROLE_ID, DILIGENZA_ROLE_ID, CHIAVE_ROLE_ID, BANKER_ROLE_ID,
    LOG_CHANNEL_ID, BANK_CHANNEL_ID, DATABASE_NAME, STAFF_ROLES,
    has_staff, has_sceriffo, has_role_id
)

# ── Bot ───────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds  = True

bot = commands.Bot(command_prefix="!", intents=intents)

print("✅ Bot inizializzato", flush=True)

# ── Import moduli (PRIMA di on_ready) ────────────────────────────────────────
_modules = [
    ("commands_wallet",          "setup_wallet_commands"),
    ("commands_rp",              "setup_rp_commands"),
    ("commands_inventory",       "setup_inventory_commands"),
    ("commands_documents",       "setup_document_commands"),
    ("commands_admin",           "setup_admin_commands"),
    ("commands_bando",           "setup_bando_commands"),
    ("commands_fines",           "setup_fine_commands"),
    ("commands_arrests",         "setup_arrest_commands"),
    ("commands_criminal_record", "setup_criminal_record_commands"),
    ("commands_fondocassa",      "setup_fondocassa_commands"),
    ("commands_robbery",         "setup_robbery_commands"),
    ("commands_theft",           "setup_theft_commands"),
    ("commands_banca",           "setup_banca_commands"),
    ("backup",                   "setup_backup_commands"),
    ("commands_usura",           "setup_usura_commands"),
    ("commands_rp_status",       "setup_rpoff_commands"),
    ("commands_invoice",         "setup_invoice_commands"),
    ("commands_wipepg",          "setup_wipepg_commands"),
    ("commands_deposits",        "setup_deposits_commands"),
    ("commands_gazzetta",        "setup_gazzetta_commands"),
]

_loaded = {}
for mod_name, func_name in _modules:
    try:
        if mod_name not in _loaded:
            _loaded[mod_name] = __import__(mod_name)
        mod = _loaded[mod_name]
        fn  = getattr(mod, func_name)
        fn(bot)
        print(f"✅ {mod_name}.{func_name}", flush=True)
    except Exception as e:
        print(f"❌ {mod_name}.{func_name}: {e}", flush=True)

print("✅ Tutti i moduli caricati!", flush=True)

# ── Events ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})", flush=True)
    print(f"✅ Server: {len(bot.guilds)}", flush=True)

    await database.init_db()

    try:
        from commands_usura import init_usura_table, task_usura_giornaliera
        await init_usura_table()
        asyncio.create_task(task_usura_giornaliera(bot))
    except Exception as e:
        print(f"⚠️ Usura: {e}", flush=True)

    await database.init_hidden_items_table()

    # Registra le View persistenti
    try:
        from commands_admin import BackgroundView
        bot.add_view(BackgroundView(bot))
        print("✅ BackgroundView registrata", flush=True)
    except Exception as e:
        print(f"⚠️ BackgroundView non registrata: {e}", flush=True)

    # ── SYNC AUTOMATICO all'avvio ─────────────────────────────────────────────
    try:
        synced = await bot.tree.sync()
        print(f"✅ Sync automatico: {len(synced)} comandi sincronizzati!", flush=True)
    except Exception as e:
        print(f"❌ Sync fallito: {e}", flush=True)

    print("🚀 Bot pronto!", flush=True)


# ── /sync manuale (se serve rifarlo) ──────────────────────────────────────────
@bot.tree.command(name="sync", description="[Owner] Sincronizza i comandi slash")
async def sync(interaction: discord.Interaction):
    if not has_role_id(interaction, STAFF_ROLE_ID):
        await interaction.response.send_message("❌ Solo i creatori del server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(
            f"✅ **{len(synced)} comandi sincronizzati!**\n🔄 Ricarica Discord.",
            ephemeral=True
        )
        print(f"✅ Sync manuale: {len(synced)} comandi (da {interaction.user})", flush=True)
    except discord.HTTPException as e:
        if e.status == 429:
            await interaction.followup.send("❌ Rate limited da Discord. Aspetta qualche minuto.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)


# ── /lista-comandi ────────────────────────────────────────────────────────────
class ListaSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="⭐ Staff",        value="staff",        description="Comandi riservati allo staff"),
            discord.SelectOption(label="🔫 Sceriffo",     value="sceriffo",     description="Comandi dello Sceriffo"),
            discord.SelectOption(label="💰 Economia",     value="economia",     description="Banca, fatture, fondo cassa"),
            discord.SelectOption(label="🤠 Roleplay",     value="roleplay",     description="Azioni RP, bisaccia, turni"),
            discord.SelectOption(label="🚫 Contrabbando", value="contrabbando", description="Raccolta e vendita droga, rapine"),
        ]
        super().__init__(placeholder="Seleziona categoria...", options=options)

    async def callback(self, interaction: discord.Interaction):
        cat = self.values[0]
        if cat == "staff":
            embed = discord.Embed(title="👮 COMANDI STAFF", color=discord.Color.red())
            cmds = [
                "`/add-money` — Aggiungi denaro a un giocatore",
                "`/remove-money` — Rimuovi denaro",
                "`/give-item` — Dai un item a un giocatore",
                "`/take-item` — Rimuovi un item",
                "`/paga-stipendio` — Paga lo stipendio",
                "`/annuncio` — Annuncio con @everyone",
                "`/bando` — Apri/chiudi bando lavorativo",
                "`/esito-bando` — Esito bando",
                "`/rpon` / `/rpoff` — Attiva/disattiva RP",
                "`/sondaggiorp` — Crea sondaggio RP",
                "`/rimuovibisaccia` — Rimuovi bisaccia giocatore",
                "`/wipe-pg` — Resetta personaggio",
                "`/wipe-item` — Svuota tutte le bisacce",
                "`/crea-item` — Crea item nell'emporio",
                "`/eliminaitem` — Elimina item emporio",
                "`/whitelister` — Esito whitelist/background",
                "`/status-whitelist` — Stato whitelist",
                "`/add-fondocassa` — Aggiungi al fondo cassa",
                "`/saldo-fondocassa` — Visualizza tutti i fondi cassa",
                "`/daiproprieta` — Registra una proprietà",
                "`/documento` — Emetti documento d'identità",
                "`/rimuovi-documento` — Rimuovi documento",
                "`/setup-background` — Invia pannello background PG",
                "`/sync` — Sincronizza comandi slash",
                "`/give-item-deposito` — Aggiungi un item al deposito di una fazione",
            ]
        elif cat == "sceriffo":
            embed = discord.Embed(title="🔫 COMANDI SCERIFFO", color=discord.Color.blue())
            cmds = [
                "`/ammanetto` — Ammanetta un sospettato",
                "`/modulo-arresto` — Compila modulo di arresto ufficiale",
                "`/taglia` — Emetti una taglia su un fuorilegge",
                "`/controlla-taglia` — Verifica le taglie di un giocatore",
                "`/paga-taglia` — Paga le taglie sulla tua testa",
                "`/puliziafedinapenale` — Pulisci la fedina penale",
                "`/cercapersona` — Cerca nel registro cittadini",
                "`/mostra-documento` — Visualizza documento di un giocatore",
                "`/controlla-saldo` — Controlla il saldo di un giocatore",
            ]
        elif cat == "economia":
            embed = discord.Embed(title="💰 COMANDI ECONOMIA", color=discord.Color.green())
            cmds = [
                "`/banca` — Accedi al tuo conto bancario",
                "`/paga` — Paga un giocatore in contanti",
                "`/fattura` — Emetti una fattura",
                "`/pagafattura` — Paga una fattura",
                "`/fondocassa` — Visualizza il fondo cassa della tua compagnia",
                "`/deposita-fondocassa` — Deposita nel fondo cassa",
                "`/preleva-fondocassa` — Preleva dal fondo cassa",
                "`/tiro-dadi` — Tira i dadi (gioco d'azzardo)",
            ]
        elif cat == "roleplay":
            embed = discord.Embed(title="🤠 COMANDI ROLEPLAY", color=discord.Color.purple())
            cmds = [
                "`/portafoglio` — Apri il tuo portafoglio",
                "`/me` — Azione RP (Fame & Sete calano)",
                "`/mangia` — Mangia dalla bisaccia",
                "`/bevi` — Bevi dalla bisaccia",
                "`/bisaccia [utente]` — Visualizza bisaccia",
                "`/vendibisaccia` — Vendi la tua bisaccia",
                "`/dai-item` — Dai un item a un altro giocatore",
                "`/utilizza-item` — Utilizza un item dalla bisaccia",
                "`/listino-emporio` — Visualizza il listino dell'emporio",
                "`/item-sell` — Acquista un item dall'emporio",
                "`/inizio-turno` / `/fine-turno` — Registra turno di lavoro",
                "`/campeggio` — Monta/smonta accampamento",
                "`/anonimo` — Invia un messaggio anonimo",
                "`/nascondo` — Nascondi un oggetto in un luogo segreto",
                "`/lettera` — Invia una lettera privata a un giocatore",
                "`/sondaggiorp` — Crea un sondaggio roleplay",
                "`/miafedinapenale` — Visualizza la tua fedina penale",
                "`/mie-proprieta` — Le tue proprietà registrate",
                "`/pulisci-arma` — Pulisci un'arma",
                "`/visualizza-stato-arma` — Visualizza l'usura delle tue armi",
                "`/depgenerici` — Visualizza il deposito della tua fazione",
                "`/mettidepfazione` — Deposita un item nel deposito",
            ]
        elif cat == "contrabbando":
            embed = discord.Embed(title="🚫 COMANDI CONTRABBANDO", color=discord.Color(0x2C2C2C))
            cmds = [
                "`/inizio-raccolta` — Inizia una sessione di raccolta droga",
                "`/fine-raccolta` — Termina la sessione",
                "`/inizio-vendita` — Inizia una sessione di vendita droga",
                "`/fine-vendita` — Termina la sessione di vendita",
                "`/rapina` — Avvia una rapina nel Far West",
                "`/inizio-creazione-alcool` — Inizia la creazione di alcool",
                "`/fine-creazione-alcool` — Termina la creazione di alcool",
                "`/inizio-distillazione` — Inizia la distillazione",
                "`/fine-distillazione` — Termina la distillazione",
                "`/inizio-vendita-moonshine` — Comincia la vendita di moonshine",
                "`/fine-vendita-moonshine` — Termina la vendita di moonshine",
            ]
        else:
            return

        embed.description = "**Comandi disponibili:**\n\n" + "\n".join(cmds)
        embed.set_footer(text="🤠 Red Dead Redemption II — Lista Comandi")
        await interaction.response.edit_message(embed=embed, view=ListaView())


class ListaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ListaSelect())


@bot.tree.command(name="lista-comandi", description="Visualizza tutti i comandi disponibili")
async def lista_comandi(interaction: discord.Interaction):
    embed = discord.Embed(
        title="<:regolamento:1459626703411478560> LISTA COMANDI — RED DEAD REDEMPTION II",
        description="Seleziona una categoria dal menu qui sotto.",
        color=discord.Color(0xDAA520), timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text="🤠 Red Dead Redemption II RP")
    await interaction.response.send_message(embed=embed, view=ListaView(), ephemeral=True)


# ── Webserver ─────────────────────────────────────────────────────────────────
async def handle(request):
    return web.Response(text="🚀 Bot Online!")

async def start_webserver():
    app_web = web.Application()
    app_web.router.add_get("/", handle)
    app_web.router.add_get("/health", handle)
    runner = web.AppRunner(app_web)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    print(f"🌐 Webserver avviato su porta {port}", flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    await start_webserver()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN mancante!", flush=True)
        return
    asyncio.create_task(backup.backup_database(bot))
    print("✅ Backup automatico avviato (ogni 6 ore)", flush=True)
    await bot.start(TOKEN)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("🚀 Avvio Red Dead Redemption II Bot...", flush=True)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot spento.", flush=True)
    except Exception as e:
        print(f"❌ Errore fatale: {e}", flush=True)
        import traceback; traceback.print_exc()
