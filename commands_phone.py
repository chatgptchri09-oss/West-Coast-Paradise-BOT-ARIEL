"""
════════════════════════════════════════════════════════════════════════════
 TELEFONO RP '93 — West Coast RP
 Sistema di telefonia anni '90 (stile Motorola MicroTAC / Nokia 1011).
 Nessun elemento moderno: niente internet, GPS, social, smartphone.
 Tutto passa per rubrica, chiamate, SMS, cercapersone e fax via Discord UI.
════════════════════════════════════════════════════════════════════════════
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
from datetime import datetime, timezone
import database
from constants import (
    LOG_CHANNEL_ID, MARKET_ROLE_ID, FORZEDELLORDINE_ROLE_ID,
    DOTTORE_ROLE_ID, MECCANICO_ROLE_ID, STAFF_ROLE_ID,
    GUILD_ID, CALL_VOICE_CATEGORY_ID
)

# ══════════════════════════════════════════════════════════════════════════════
#  ⚠️ CANALI DA CONFIGURARE — al momento a 0 (nessun invio) finché non mi dai
#     gli ID reali. Il comando funziona comunque, semplicemente non pinga
#     nessun canale finché questi restano a 0.
# ══════════════════════════════════════════════════════════════════════════════
CANALE_POLIZIA    = 1532351156712505495   # Cercapersone/emergenza Polizia
CANALE_EMS        = 1532351192175345786   # Cercapersone/emergenza EMS
CANALE_TAXI       = 1532351240850247803   # Chiamata emergenza Taxi
CANALE_MECCANICO  = 1532351313097003058   # Cercapersone/emergenza Meccanico
CANALE_QUESTURA   = 1532351380906315948   # Fax — Questura
CANALE_OSPEDALE   = 1532351409213673522   # Fax — Ospedale
CANALE_MUNICIPIO  = 1532351452033449994   # Fax — Municipio
CANALE_TRIBUNALE  = 1532351483935326228# Fax — Tribunale

TASSISTA_ROLE_ID = 1431547525378347050
GIUSTIZIA_ROLE_ID = 1415244214329151508

# ── Colori tema anni '90 (grigio/verde/blu scuro) ─────────────────────────────
COLOR_PHONE   = 0x2F3336   # grigio scuro corpo telefono
COLOR_SCREEN  = 0x1B3B2F   # verde schermo LCD
COLOR_CALL    = 0x0B3D5C   # blu scuro chiamata
COLOR_ALERT   = 0x8B0000

BATTERIA_COSTO_CHIAMATA = 6
BATTERIA_COSTO_SMS      = 2
COSTO_SMS_BOLLETTA      = 2       # $ per SMS inviato
COSTO_CHIAMATA_BOLLETTA = 5       # $ per chiamata effettuata
BOLLETTA_INTERVALLO_H   = 24      # ogni quante ore si genera la bolletta

# ── Canale vocale privato di chiamata ─────────────────────────────────────────
CANALE_CHIAMATA_MAX_ATTESE   = 80   # 80 * 15s = 20 minuti di vita massima
CANALE_CHIAMATA_VUOTO_LIMITE = 30   # secondi a canale vuoto prima di eliminarlo

# ── Enti pubblici abilitati al Fax ────────────────────────────────────────────
ENTI_FAX = {
    "Questura":   {"ruolo": FORZEDELLORDINE_ROLE_ID, "canale": CANALE_QUESTURA,  "emoji": "🚔"},
    "Ospedale":   {"ruolo": DOTTORE_ROLE_ID,          "canale": CANALE_OSPEDALE,  "emoji": "🏥"},
    "Municipio":  {"ruolo": GIUSTIZIA_ROLE_ID,            "canale": CANALE_MUNICIPIO, "emoji": "🏛️"},  # ⚠️ ruolo placeholder
    "Tribunale":  {"ruolo": GIUSTIZIA_ROLE_ID,            "canale": CANALE_TRIBUNALE, "emoji": "⚖️"},   # ⚠️ ruolo placeholder
}

# ── Elenco telefonico attività (flavor RP, numeri fittizi ma coerenti) ────────
ELENCO_ATTIVITA = {
    "🚔 Questura di Los Santos":  "+1 911-000",
    "🏥 Ospedale Centrale":       "+1 911-100",
    "🔧 Beeker Garage":           "+1 555-0142",
    "🚗 Concessionario":          "+1 555-0187",
    "🏦 Palomino Bank":           "+1 555-0100",
    "🍻 Yellow Jack Bar":         "+1 555-0199",
    "🍩 County Donuts":           "+1 555-0175",
    "✈️ Pegasus Hangar":          "+1 555-0160",
}

# ── Cercapersone: enti disponibili ────────────────────────────────────────────
ENTI_PAGER = {
    "Polizia":    {"canale": CANALE_POLIZIA,   "emoji": "🚔", "ruolo_ping": FORZEDELLORDINE_ROLE_ID},
    "EMS":        {"canale": CANALE_EMS,       "emoji": "🏥", "ruolo_ping": DOTTORE_ROLE_ID},
    "Meccanico":  {"canale": CANALE_MECCANICO, "emoji": "🔧", "ruolo_ping": MECCANICO_ROLE_ID},
}

# ── Numeri di emergenza rapidi ────────────────────────────────────────────────
NUMERI_EMERGENZA = {
    "Polizia":    {"canale": CANALE_POLIZIA,   "emoji": "🚔", "ruolo_ping": FORZEDELLORDINE_ROLE_ID},
    "EMS":        {"canale": CANALE_EMS,       "emoji": "🏥", "ruolo_ping": DOTTORE_ROLE_ID},
    "Taxi":       {"canale": CANALE_TAXI,      "emoji": "🚕", "ruolo_ping": TASSISTA_ROLE_ID},
    "Meccanico":  {"canale": CANALE_MECCANICO, "emoji": "🔧", "ruolo_ping": MECCANICO_ROLE_ID},
}

# Chiamate attive in memoria: numero -> {"partner": numero, "msg_caller":..., "msg_target":...}
_chiamate_attive: dict = {}


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER
# ══════════════════════════════════════════════════════════════════════════════

async def _display_name_for(numero: str, bot: commands.Bot) -> str:
    """Nome da mostrare per un numero: se è una rubrica nota lo gestiamo altrove;
    qui ritorniamo solo il display name Discord del proprietario, se trovabile."""
    phone = await database.get_phone_by_number(numero)
    if not phone:
        return numero
    try:
        user = await bot.fetch_user(int(phone["user_id"]))
        return user.display_name if user else numero
    except Exception:
        return numero


def _batteria_bar(v: int) -> str:
    pieni = round(v / 10)
    return "🟩" * pieni + "⬛" * (10 - pieni) + f"  {v}%"


async def _richiedi_telefono(interaction: discord.Interaction) -> dict | None:
    """Verifica che l'utente possieda un telefono. Se no, avvisa e ritorna None."""
    phone = await database.get_phone(str(interaction.user.id))
    if not phone:
        await interaction.response.send_message(
            "❌ Non possiedi un telefono! Vai al **Market** in RP per acquistarne uno.",
            ephemeral=True
        )
        return None
    return phone


# ══════════════════════════════════════════════════════════════════════════════
#  CANALE VOCALE PRIVATO DI CHIAMATA
# ══════════════════════════════════════════════════════════════════════════════

async def _crea_canale_privato_chiamata(bot: commands.Bot, caller: discord.User, target: discord.User) -> discord.VoiceChannel | None:
    """Crea un canale vocale visibile/accessibile solo ai 2 utenti in chiamata.
    Ritorna None (con log di errore) se guild/categoria non sono configurate o
    se manca il permesso di gestione canali."""
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print(f"❌ [Telefono] GUILD_ID {GUILD_ID} non trovato: impossibile creare il canale chiamata.", flush=True)
        return None

    category = guild.get_channel(CALL_VOICE_CATEGORY_ID) if CALL_VOICE_CATEGORY_ID else None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True),
    }

    caller_member = guild.get_member(caller.id)
    target_member = guild.get_member(target.id)
    if caller_member:
        overwrites[caller_member] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
    if target_member:
        overwrites[target_member] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)

    nome_canale = f"📞-{caller.display_name}-{target.display_name}"[:100]

    try:
        canale = await guild.create_voice_channel(
            name=nome_canale,
            category=category,
            overwrites=overwrites,
            reason=f"Canale privato chiamata telefonica RP tra {caller} e {target}"
        )
    except discord.Forbidden:
        print("❌ [Telefono] Permessi insufficienti per creare il canale vocale della chiamata.", flush=True)
        return None
    except Exception as e:
        print(f"❌ [Telefono] Errore creazione canale chiamata: {e}", flush=True)
        return None

    asyncio.create_task(_monitora_canale_chiamata(bot, canale.id, guild.id))
    return canale


async def _monitora_canale_chiamata(bot: commands.Bot, canale_id: int, guild_id: int):
    """Elimina automaticamente il canale chiamata quando resta vuoto per
    CANALE_CHIAMATA_VUOTO_LIMITE secondi, o comunque dopo un tetto massimo
    di CANALE_CHIAMATA_MAX_ATTESE cicli, per non lasciare canali orfani."""
    vuoto_da = 0
    for _ in range(CANALE_CHIAMATA_MAX_ATTESE):
        await asyncio.sleep(15)
        guild = bot.get_guild(guild_id)
        if not guild:
            return
        canale = guild.get_channel(canale_id)
        if canale is None:
            return  # già eliminato
        if len(canale.members) == 0:
            vuoto_da += 15
            if vuoto_da >= CANALE_CHIAMATA_VUOTO_LIMITE:
                try:
                    await canale.delete(reason="Chiamata terminata - canale vocale vuoto")
                except Exception:
                    pass
                return
        else:
            vuoto_da = 0

    # Tetto massimo raggiunto: elimina comunque il canale
    guild = bot.get_guild(guild_id)
    if guild:
        canale = guild.get_channel(canale_id)
        if canale:
            try:
                await canale.delete(reason="Timeout massimo canale chiamata")
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
#  MODAL — Aggiungi/Modifica contatto
# ══════════════════════════════════════════════════════════════════════════════
class ContattoModal(discord.ui.Modal):
    numero = discord.ui.TextInput(label="Numero di telefono", placeholder="Es: +1 555-0123", required=True, max_length=30)
    nome   = discord.ui.TextInput(label="Nome contatto", placeholder="Es: Mario", required=True, max_length=50)

    def __init__(self, owner_id: str, modifica: bool = False, numero_esistente: str = None):
        super().__init__(title="✏️ Modifica Contatto" if modifica else "📇 Nuovo Contatto")
        self.owner_id = owner_id
        self.modifica = modifica
        if modifica and numero_esistente:
            self.numero.default = numero_esistente

    async def on_submit(self, interaction: discord.Interaction):
        numero_val = self.numero.value.strip()
        if self.modifica:
            ok = await database.update_contact(self.owner_id, numero_val, self.nome.value.strip())
            msg = "✅ Contatto aggiornato." if ok else "❌ Contatto non trovato."
        else:
            if numero_val == (await database.get_phone(self.owner_id))["numero"]:
                await interaction.response.send_message("❌ Non puoi aggiungere il tuo stesso numero.", ephemeral=True)
                return
            ok = await database.add_contact(self.owner_id, numero_val, self.nome.value.strip())
            msg = f"✅ **{self.nome.value}** aggiunto alla rubrica." if ok else "❌ Hai già questo numero in rubrica."
        await interaction.response.send_message(msg, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
#  MODAL — Chiamata
# ══════════════════════════════════════════════════════════════════════════════
class ChiamaModal(discord.ui.Modal, title="📞 Effettua Chiamata"):
    numero = discord.ui.TextInput(label="Numero da chiamare", placeholder="Es: +1 555-0123", required=True, max_length=30)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await _avvia_chiamata(interaction, self.bot, self.numero.value.strip())


async def _avvia_chiamata(interaction: discord.Interaction, bot: commands.Bot, numero_dest: str):
    uid = str(interaction.user.id)
    mio_phone = await database.get_phone(uid)

    if not mio_phone["acceso"]:
        await interaction.response.send_message("❌ Il tuo telefono è spento!", ephemeral=True)
        return
    if mio_phone["batteria"] < BATTERIA_COSTO_CHIAMATA:
        await interaction.response.send_message("🔋 Batteria troppo scarica per chiamare! Ricaricalo dalle Impostazioni.", ephemeral=True)
        return
    if numero_dest == mio_phone["numero"]:
        await interaction.response.send_message("❌ Non puoi chiamare te stesso.", ephemeral=True)
        return

    dest_phone = await database.get_phone_by_number(numero_dest)
    if not dest_phone:
        await interaction.response.send_message(f"❌ Nessun telefono registrato con il numero **{numero_dest}**.", ephemeral=True)
        return

    if numero_dest in _chiamate_attive or mio_phone["numero"] in _chiamate_attive:
        await interaction.response.send_message("❌ Linea occupata: una chiamata è già in corso.", ephemeral=True)
        return

    if not dest_phone["acceso"]:
        await database.log_call(uid, numero_dest, None, "persa")
        await interaction.response.send_message(
            f"📵 Il numero **{numero_dest}** ha il telefono spento. Chiamata non riuscita.", ephemeral=True
        )
        return

    try:
        dest_user = await bot.fetch_user(int(dest_phone["user_id"]))
    except Exception:
        dest_user = None

    if dest_user is None:
        await interaction.response.send_message("❌ Impossibile raggiungere questo numero al momento.", ephemeral=True)
        return

    await database.adjust_battery(uid, -BATTERIA_COSTO_CHIAMATA)
    await interaction.response.send_message(f"📞 Chiamata in corso verso **{numero_dest}**...", ephemeral=True)

    embed_richiesta = discord.Embed(
        title="📞 𝐂𝐇𝐈𝐀𝐌𝐀𝐓𝐀 𝐈𝐍 𝐀𝐑𝐑𝐈𝐕𝐎",
        description=f"**{mio_phone['numero']}** ({interaction.user.display_name}) ti sta chiamando...",
        color=COLOR_CALL,
        timestamp=discord.utils.utcnow()
    )
    embed_richiesta.set_footer(text="🏙️ West Coast RP '93 — Telefono")

    view = RispostaChiamataView(bot, interaction.user, dest_user, mio_phone["numero"], numero_dest)

    try:
        msg = await dest_user.send(embed=embed_richiesta, view=view)
        view.msg = msg
    except discord.Forbidden:
        await database.log_call(uid, numero_dest, None, "persa")
        await interaction.followup.send("❌ Il destinatario ha i DM chiusi: chiamata non recapitata.", ephemeral=True)
        return

    _chiamate_attive[mio_phone["numero"]] = numero_dest
    _chiamate_attive[numero_dest] = mio_phone["numero"]

    # Timeout automatico 30s → chiamata persa
    async def _timeout_check():
        await asyncio.sleep(30)
        if mio_phone["numero"] in _chiamate_attive and not view.risposta_data:
            _chiamate_attive.pop(mio_phone["numero"], None)
            _chiamate_attive.pop(numero_dest, None)
            await database.log_call(uid, numero_dest, None, "persa")
            await database.log_call(dest_phone["user_id"], mio_phone["numero"], None, "persa")
            try:
                for c in view.children:
                    c.disabled = True
                await msg.edit(content="⏰ Chiamata persa (nessuna risposta).", view=view)
            except Exception:
                pass
            try:
                await interaction.followup.send(f"📵 **{numero_dest}** non ha risposto. Chiamata persa.", ephemeral=True)
            except Exception:
                pass

    asyncio.create_task(_timeout_check())


class RispostaChiamataView(discord.ui.View):
    def __init__(self, bot, caller: discord.User, target: discord.User, numero_caller: str, numero_target: str):
        super().__init__(timeout=35)
        self.bot           = bot
        self.caller        = caller
        self.target        = target
        self.numero_caller = numero_caller
        self.numero_target = numero_target
        self.risposta_data = False
        self.msg           = None

    @discord.ui.button(label="✅ Rispondi", style=discord.ButtonStyle.green)
    async def rispondi(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ Non è la tua chiamata.", ephemeral=True)
            return
        self.risposta_data = True
        _chiamate_attive.pop(self.numero_caller, None)
        _chiamate_attive.pop(self.numero_target, None)

        await database.log_call(str(self.caller.id), self.numero_target, None, "effettuata")
        await database.log_call(str(self.target.id), self.numero_caller, None, "ricevuta")

        for c in self.children:
            c.disabled = True

        # Crea il canale vocale privato riservato ai 2 partecipanti
        canale = await _crea_canale_privato_chiamata(self.bot, self.caller, self.target)
        if canale:
            testo_canale = f"🔊 Canale vocale privato: {canale.mention}"
        else:
            testo_canale = "⚠️ Canale vocale non creato (configurazione mancante o permessi insufficienti — avvisa lo Staff)."

        embed = discord.Embed(
            title="☎️ 𝐂𝐡𝐢𝐚𝐦𝐚𝐭𝐚 𝐢𝐧 𝐜𝐨𝐫𝐬𝐨",
            description=f"Sei in linea con **{self.numero_caller}**.\n{testo_canale}",
            color=COLOR_CALL
        )
        embed.set_footer(text="🏙️ West Coast RP '93 — Telefono")
        await interaction.response.edit_message(embed=embed, view=self)

        try:
            await self.caller.send(embed=discord.Embed(
                title="✅ Chiamata Accettata",
                description=f"**{self.numero_target}** ha risposto! Sei in linea.\n{testo_canale}",
                color=COLOR_CALL
            ))
        except Exception:
            pass

    @discord.ui.button(label="❌ Rifiuta", style=discord.ButtonStyle.red)
    async def rifiuta(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ Non è la tua chiamata.", ephemeral=True)
            return
        self.risposta_data = True
        _chiamate_attive.pop(self.numero_caller, None)
        _chiamate_attive.pop(self.numero_target, None)

        await database.log_call(str(self.caller.id), self.numero_target, None, "persa")
        await database.log_call(str(self.target.id), self.numero_caller, None, "persa")

        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(content="❌ Chiamata rifiutata.", embed=None, view=self)

        try:
            await self.caller.send(f"📵 **{self.numero_target}** ha rifiutato la chiamata.")
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  MODAL — SMS
# ══════════════════════════════════════════════════════════════════════════════
class SmsModal(discord.ui.Modal, title="💬 Nuovo SMS"):
    numero = discord.ui.TextInput(label="Numero destinatario", placeholder="Es: +1 555-0123", required=True, max_length=30)
    testo  = discord.ui.TextInput(label="Messaggio", style=discord.TextStyle.paragraph, max_length=300, required=True)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        mio_phone = await database.get_phone(uid)

        if not mio_phone["acceso"]:
            await interaction.response.send_message("❌ Il tuo telefono è spento!", ephemeral=True)
            return
        if mio_phone["batteria"] < BATTERIA_COSTO_SMS:
            await interaction.response.send_message("🔋 Batteria troppo scarica per inviare SMS!", ephemeral=True)
            return

        dest_numero = self.numero.value.strip()
        dest_phone  = await database.get_phone_by_number(dest_numero)
        if not dest_phone:
            await interaction.response.send_message(f"❌ Nessun telefono registrato con il numero **{dest_numero}**.", ephemeral=True)
            return
        if dest_numero == mio_phone["numero"]:
            await interaction.response.send_message("❌ Non puoi mandare un SMS a te stesso.", ephemeral=True)
            return

        await database.adjust_battery(uid, -BATTERIA_COSTO_SMS)
        await database.send_sms(mio_phone["numero"], uid, dest_numero, dest_phone["user_id"], self.testo.value)

        embed = discord.Embed(
            title="💬 𝐒𝐌𝐒 𝐈𝐧𝐯𝐢𝐚𝐭𝐨",
            color=COLOR_SCREEN,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📤 A", value=dest_numero, inline=True)
        embed.add_field(name="💬 Testo", value=self.testo.value, inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Telefono")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        if dest_phone["acceso"] and not dest_phone["silenzioso"]:
            try:
                dest_user = await self.bot.fetch_user(int(dest_phone["user_id"]))
                dm = discord.Embed(
                    title="💬 Nuovo SMS ricevuto",
                    description=f"**Da:** {mio_phone['numero']}\n\n*{self.testo.value}*",
                    color=COLOR_SCREEN,
                    timestamp=discord.utils.utcnow()
                )
                dm.set_footer(text="🏙️ West Coast RP '93 — Telefono | Usa /telefono per rispondere")
                await dest_user.send(embed=dm)
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
#  MODAL — Cambia suoneria
# ══════════════════════════════════════════════════════════════════════════════
class SuoneriaModal(discord.ui.Modal, title="🔔 Cambia Suoneria"):
    nome = discord.ui.TextInput(label="Nome suoneria (solo RP)", placeholder="Es: Classica, Nokia Tune, Silenzio...", required=True, max_length=40)

    async def on_submit(self, interaction: discord.Interaction):
        await database.set_phone_suoneria(str(interaction.user.id), self.nome.value.strip())
        await interaction.response.send_message(f"🔔 Suoneria impostata su **{self.nome.value}**.", ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
#  MODAL — Cercapersone / Emergenza (messaggio breve)
# ══════════════════════════════════════════════════════════════════════════════
class MessaggioBreveModal(discord.ui.Modal):
    messaggio = discord.ui.TextInput(label="Messaggio", style=discord.TextStyle.paragraph, max_length=200, required=True)

    def __init__(self, bot: commands.Bot, ente: str, config: dict, tipo: str):
        super().__init__(title=f"{config['emoji']} {tipo} — {ente}")
        self.bot    = bot
        self.ente   = ente
        self.config = config
        self.tipo   = tipo

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"{self.config['emoji']} {self.tipo.upper()} — {self.ente}",
            description=self.messaggio.value,
            color=COLOR_ALERT if self.tipo == "Emergenza" else COLOR_CALL,
            timestamp=discord.utils.utcnow()
        )
        mio_phone = await database.get_phone(str(interaction.user.id))
        embed.add_field(name="📞 Numero chiamante", value=mio_phone["numero"] if mio_phone else "Sconosciuto", inline=True)
        embed.add_field(name="👤 Cittadino", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Telefono")

        canale_id = self.config["canale"]
        inviato = False
        if canale_id:
            ch = self.bot.get_channel(canale_id)
            if ch:
                ping = f"<@&{self.config['ruolo_ping']}>" if self.config.get("ruolo_ping") else ""
                await ch.send(content=ping, embed=embed)
                inviato = True

        if inviato:
            await interaction.response.send_message(f"✅ {self.tipo} inviata a **{self.ente}**.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"⚠️ Messaggio registrato ma il canale di **{self.ente}** non è ancora configurato. Avvisa lo Staff.",
                ephemeral=True
            )


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW — Menu principale del telefono
# ══════════════════════════════════════════════════════════════════════════════
class TelefonoMenuView(discord.ui.View):
    def __init__(self, bot: commands.Bot, owner_id: str):
        super().__init__(timeout=180)
        self.bot      = bot
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("❌ Questo non è il tuo telefono!", ephemeral=True)
            return False
        return True

    async def _build_home_embed(self) -> discord.Embed:
        phone = await database.get_phone(self.owner_id)
        stato = "🟢 Acceso" if phone["acceso"] else "🔴 Spento"
        silenzioso = " 🔇" if phone["silenzioso"] else ""
        embed = discord.Embed(
            title="📱 𝐓𝐞𝐥𝐞𝐟𝐨𝐧𝐨 '𝟗𝟑",
            description=f"**Numero:** `{phone['numero']}`\n**Stato:** {stato}{silenzioso}",
            color=COLOR_PHONE,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🔋 Batteria", value=_batteria_bar(phone["batteria"]), inline=False)
        embed.add_field(name="🔔 Suoneria", value=phone["suoneria"], inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Telefono")
        return embed

    @discord.ui.button(label="Rubrica", emoji="📇", style=discord.ButtonStyle.secondary, row=0)
    async def rubrica(self, interaction: discord.Interaction, button: discord.ui.Button):
        contatti = await database.get_contacts(self.owner_id)
        embed = discord.Embed(title="📇 𝐑𝐮𝐛𝐫𝐢𝐜𝐚", color=COLOR_SCREEN, timestamp=discord.utils.utcnow())
        if not contatti:
            embed.description = "*Rubrica vuota.*"
        else:
            embed.description = "\n".join(f"**{c['nome']}** — `{c['numero']}`" for c in contatti[:25])
        embed.set_footer(text="🏙️ West Coast RP '93 — Telefono")
        await interaction.response.edit_message(embed=embed, view=RubricaView(self.bot, self.owner_id, contatti))

    @discord.ui.button(label="Chiama", emoji="📞", style=discord.ButtonStyle.success, row=0)
    async def chiama(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChiamaModal(self.bot))

    @discord.ui.button(label="SMS", emoji="💬", style=discord.ButtonStyle.success, row=0)
    async def sms(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SmsModal(self.bot))

    @discord.ui.button(label="Conversazioni", emoji="🗂️", style=discord.ButtonStyle.secondary, row=1)
    async def conversazioni(self, interaction: discord.Interaction, button: discord.ui.Button):
        partner = await database.get_conversation_partners(self.owner_id)
        embed = discord.Embed(title="🗂️ 𝐂𝐨𝐧𝐯𝐞𝐫𝐬𝐚𝐳𝐢𝐨𝐧𝐢", color=COLOR_SCREEN, timestamp=discord.utils.utcnow())
        if not partner:
            embed.description = "*Nessuna conversazione SMS.*"
            await interaction.response.edit_message(embed=embed, view=self)
            return
        embed.description = "Seleziona una conversazione da aprire."
        await interaction.response.edit_message(embed=embed, view=ConversazioniView(self.bot, self.owner_id, partner))

    @discord.ui.button(label="Registro", emoji="📜", style=discord.ButtonStyle.secondary, row=1)
    async def registro(self, interaction: discord.Interaction, button: discord.ui.Button):
        chiamate = await database.get_call_log(self.owner_id)
        embed = discord.Embed(title="📜 𝐑𝐞𝐠𝐢𝐬𝐭𝐫𝐨 𝐂𝐡𝐢𝐚𝐦𝐚𝐭𝐞", color=COLOR_SCREEN, timestamp=discord.utils.utcnow())
        if not chiamate:
            embed.description = "*Nessuna chiamata registrata.*"
        else:
            icona = {"effettuata": "📤", "ricevuta": "📥", "persa": "📵"}
            righe = [f"{icona.get(c['tipo'],'📞')} `{c['numero_altro']}` — {c['tipo']} — {c['created_at']}" for c in chiamate]
            embed.description = "\n".join(righe)
        embed.set_footer(text="🏙️ West Coast RP '93 — Telefono")
        await interaction.response.edit_message(embed=embed, view=RegistroView(self.bot, self.owner_id))

    @discord.ui.button(label="Cercapersone", emoji="📟", style=discord.ButtonStyle.primary, row=2)
    async def cercapersone(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📟 𝐂𝐞𝐫𝐜𝐚𝐩𝐞𝐫𝐬𝐨𝐧𝐞",
            description="Seleziona l'ente da contattare per un messaggio breve.",
            color=COLOR_CALL
        )
        await interaction.response.edit_message(embed=embed, view=PagerView(self.bot, self.owner_id))

    @discord.ui.button(label="Emergenza", emoji="🚨", style=discord.ButtonStyle.danger, row=2)
    async def emergenza(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🚨 𝐍𝐮𝐦𝐞𝐫𝐢 𝐝𝐢 𝐄𝐦𝐞𝐫𝐠𝐞𝐧𝐳𝐚",
            description="Seleziona il servizio da contattare urgentemente.",
            color=COLOR_ALERT
        )
        await interaction.response.edit_message(embed=embed, view=EmergenzaView(self.bot, self.owner_id))

    @discord.ui.button(label="Elenco Attività", emoji="🏢", style=discord.ButtonStyle.secondary, row=3)
    async def elenco(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏢 𝐄𝐥𝐞𝐧𝐜𝐨 𝐓𝐞𝐥𝐞𝐟𝐨𝐧𝐢𝐜𝐨 𝐀𝐭𝐭𝐢𝐯𝐢𝐭à", color=COLOR_SCREEN, timestamp=discord.utils.utcnow())
        embed.description = "\n".join(f"**{nome}** — `{numero}`" for nome, numero in ELENCO_ATTIVITA.items())
        embed.set_footer(text="🏙️ West Coast RP '93 — Telefono")
        await interaction.response.edit_message(embed=embed, view=BackHomeView(self.bot, self.owner_id))

    @discord.ui.button(label="Impostazioni", emoji="⚙️", style=discord.ButtonStyle.secondary, row=3)
    async def impostazioni(self, interaction: discord.Interaction, button: discord.ui.Button):
        phone = await database.get_phone(self.owner_id)
        embed = discord.Embed(title="⚙️ 𝐈𝐦𝐩𝐨𝐬𝐭𝐚𝐳𝐢𝐨𝐧𝐢", color=COLOR_PHONE, timestamp=discord.utils.utcnow())
        embed.add_field(name="🔋 Batteria", value=_batteria_bar(phone["batteria"]), inline=False)
        embed.add_field(name="🔔 Suoneria", value=phone["suoneria"], inline=True)
        embed.add_field(name="🔇 Silenzioso", value="Attivo" if phone["silenzioso"] else "Disattivo", inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Telefono")
        await interaction.response.edit_message(embed=embed, view=ImpostazioniView(self.bot, self.owner_id, phone))


class BackHomeView(discord.ui.View):
    def __init__(self, bot, owner_id):
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.owner_id

    @discord.ui.button(label="⬅️ Indietro", style=discord.ButtonStyle.secondary)
    async def indietro(self, interaction: discord.Interaction, button: discord.ui.Button):
        menu = TelefonoMenuView(self.bot, self.owner_id)
        embed = await menu._build_home_embed()
        await interaction.response.edit_message(embed=embed, view=menu)


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW — Rubrica
# ══════════════════════════════════════════════════════════════════════════════
class RubricaView(discord.ui.View):
    def __init__(self, bot, owner_id, contatti):
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.contatti = contatti
        if contatti:
            self.add_item(RubricaSelect(contatti))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.owner_id

    @discord.ui.button(label="➕ Aggiungi", style=discord.ButtonStyle.success, row=1)
    async def aggiungi(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ContattoModal(self.owner_id))

    @discord.ui.button(label="⬅️ Indietro", style=discord.ButtonStyle.secondary, row=1)
    async def indietro(self, interaction: discord.Interaction, button: discord.ui.Button):
        menu = TelefonoMenuView(self.bot, self.owner_id)
        embed = await menu._build_home_embed()
        await interaction.response.edit_message(embed=embed, view=menu)


class RubricaSelect(discord.ui.Select):
    def __init__(self, contatti):
        options = [
            discord.SelectOption(label=c["nome"][:100], description=c["numero"], value=c["numero"])
            for c in contatti[:25]
        ]
        super().__init__(placeholder="Seleziona un contatto per gestirlo...", options=options)

    async def callback(self, interaction: discord.Interaction):
        numero = self.values[0]
        view = discord.ui.View(timeout=60)

        async def modifica_cb(itr: discord.Interaction):
            await itr.response.send_modal(ContattoModal(str(interaction.user.id), modifica=True, numero_esistente=numero))

        async def elimina_cb(itr: discord.Interaction):
            ok = await database.delete_contact(str(interaction.user.id), numero)
            await itr.response.send_message("🗑️ Contatto eliminato." if ok else "❌ Errore.", ephemeral=True)

        btn_mod = discord.ui.Button(label="✏️ Modifica", style=discord.ButtonStyle.primary)
        btn_mod.callback = modifica_cb
        btn_del = discord.ui.Button(label="🗑️ Elimina", style=discord.ButtonStyle.danger)
        btn_del.callback = elimina_cb
        view.add_item(btn_mod)
        view.add_item(btn_del)

        await interaction.response.send_message(f"Gestisci il contatto `{numero}`:", view=view, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW — Conversazioni SMS
# ══════════════════════════════════════════════════════════════════════════════
class ConversazioniView(discord.ui.View):
    def __init__(self, bot, owner_id, partners):
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        if partners:
            self.add_item(ConversazioniSelect(owner_id, partners))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.owner_id

    @discord.ui.button(label="⬅️ Indietro", style=discord.ButtonStyle.secondary, row=1)
    async def indietro(self, interaction: discord.Interaction, button: discord.ui.Button):
        menu = TelefonoMenuView(self.bot, self.owner_id)
        embed = await menu._build_home_embed()
        await interaction.response.edit_message(embed=embed, view=menu)


class ConversazioniSelect(discord.ui.Select):
    def __init__(self, owner_id, partners):
        options = [discord.SelectOption(label=p, value=p) for p in partners[:25]]
        super().__init__(placeholder="Apri una conversazione...", options=options)
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        numero_altro = self.values[0]
        messaggi = await database.get_conversation(self.owner_id, numero_altro)
        embed = discord.Embed(title=f"💬 Conversazione con {numero_altro}", color=COLOR_SCREEN, timestamp=discord.utils.utcnow())
        if not messaggi:
            embed.description = "*Nessun messaggio.*"
        else:
            righe = []
            for m in messaggi:
                mittente = "Tu" if m["mittente_id"] == self.owner_id else numero_altro
                righe.append(f"**{mittente}:** {m['testo']}")
            embed.description = "\n".join(righe)[:4000]
        embed.set_footer(text="🏙️ West Coast RP '93 — Telefono")

        view = discord.ui.View(timeout=60)
        async def elimina_cb(itr: discord.Interaction):
            await database.delete_conversation(self.owner_id, numero_altro)
            await itr.response.send_message("🗑️ Conversazione eliminata.", ephemeral=True)
        btn = discord.ui.Button(label="🗑️ Elimina conversazione", style=discord.ButtonStyle.danger)
        btn.callback = elimina_cb
        view.add_item(btn)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW — Registro chiamate
# ══════════════════════════════════════════════════════════════════════════════
class RegistroView(discord.ui.View):
    def __init__(self, bot, owner_id):
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.owner_id

    @discord.ui.button(label="🗑️ Cancella registro", style=discord.ButtonStyle.danger, row=0)
    async def cancella(self, interaction: discord.Interaction, button: discord.ui.Button):
        await database.clear_call_log(self.owner_id)
        await interaction.response.send_message("🗑️ Registro chiamate cancellato.", ephemeral=True)

    @discord.ui.button(label="⬅️ Indietro", style=discord.ButtonStyle.secondary, row=0)
    async def indietro(self, interaction: discord.Interaction, button: discord.ui.Button):
        menu = TelefonoMenuView(self.bot, self.owner_id)
        embed = await menu._build_home_embed()
        await interaction.response.edit_message(embed=embed, view=menu)


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW — Impostazioni
# ══════════════════════════════════════════════════════════════════════════════
class ImpostazioniView(discord.ui.View):
    def __init__(self, bot, owner_id, phone):
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.phone = phone

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.owner_id

    @discord.ui.button(label="Spegni/Accendi", emoji="🔌", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_power(self, interaction: discord.Interaction, button: discord.ui.Button):
        nuovo = not self.phone["acceso"]
        await database.set_phone_power(self.owner_id, nuovo)
        await interaction.response.send_message(f"📱 Telefono {'🟢 acceso' if nuovo else '🔴 spento'}.", ephemeral=True)

    @discord.ui.button(label="Silenzioso", emoji="🔇", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_silenzioso(self, interaction: discord.Interaction, button: discord.ui.Button):
        nuovo = not self.phone["silenzioso"]
        await database.set_phone_silenzioso(self.owner_id, nuovo)
        await interaction.response.send_message(f"🔇 Modalità silenziosa {'attivata' if nuovo else 'disattivata'}.", ephemeral=True)

    @discord.ui.button(label="Suoneria", emoji="🔔", style=discord.ButtonStyle.secondary, row=1)
    async def suoneria(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SuoneriaModal())

    @discord.ui.button(label="Ricarica batteria", emoji="🔋", style=discord.ButtonStyle.success, row=1)
    async def ricarica(self, interaction: discord.Interaction, button: discord.ui.Button):
        await database.recharge_battery(self.owner_id)
        await interaction.response.send_message("🔋 Batteria ricaricata al 100%.", ephemeral=True)

    @discord.ui.button(label="⬅️ Indietro", emoji="↩️", style=discord.ButtonStyle.secondary, row=2)
    async def indietro(self, interaction: discord.Interaction, button: discord.ui.Button):
        menu = TelefonoMenuView(self.bot, self.owner_id)
        embed = await menu._build_home_embed()
        await interaction.response.edit_message(embed=embed, view=menu)


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW — Cercapersone
# ══════════════════════════════════════════════════════════════════════════════
class PagerView(discord.ui.View):
    def __init__(self, bot, owner_id):
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.add_item(PagerSelect(bot))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.owner_id

    @discord.ui.button(label="⬅️ Indietro", style=discord.ButtonStyle.secondary, row=1)
    async def indietro(self, interaction: discord.Interaction, button: discord.ui.Button):
        menu = TelefonoMenuView(self.bot, self.owner_id)
        embed = await menu._build_home_embed()
        await interaction.response.edit_message(embed=embed, view=menu)


class PagerSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [discord.SelectOption(label=f"{cfg['emoji']} {ente}", value=ente) for ente, cfg in ENTI_PAGER.items()]
        super().__init__(placeholder="Seleziona l'ente da cercare...", options=options)

    async def callback(self, interaction: discord.Interaction):
        ente = self.values[0]
        cfg  = ENTI_PAGER[ente]
        await interaction.response.send_modal(MessaggioBreveModal(self.bot, ente, cfg, "Cercapersone"))


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW — Emergenza
# ══════════════════════════════════════════════════════════════════════════════
class EmergenzaView(discord.ui.View):
    def __init__(self, bot, owner_id):
        super().__init__(timeout=180)
        self.bot = bot
        self.owner_id = owner_id
        self.add_item(EmergenzaSelect(bot))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.owner_id

    @discord.ui.button(label="⬅️ Indietro", style=discord.ButtonStyle.secondary, row=1)
    async def indietro(self, interaction: discord.Interaction, button: discord.ui.Button):
        menu = TelefonoMenuView(self.bot, self.owner_id)
        embed = await menu._build_home_embed()
        await interaction.response.edit_message(embed=embed, view=menu)


class EmergenzaSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [discord.SelectOption(label=f"{cfg['emoji']} {ente}", value=ente) for ente, cfg in NUMERI_EMERGENZA.items()]
        super().__init__(placeholder="Seleziona il servizio d'emergenza...", options=options)

    async def callback(self, interaction: discord.Interaction):
        ente = self.values[0]
        cfg  = NUMERI_EMERGENZA[ente]
        await interaction.response.send_modal(MessaggioBreveModal(self.bot, ente, cfg, "Emergenza"))


# ══════════════════════════════════════════════════════════════════════════════
#  TASK — Bolletta periodica
# ══════════════════════════════════════════════════════════════════════════════
async def task_bolletta_periodica(bot: commands.Bot):
    """Ogni BOLLETTA_INTERVALLO_H ore genera una bolletta per l'utilizzo del telefono."""
    await database.init_phone_tables()
    await bot.wait_until_ready()
    print("📱 Task bolletta telefonica avviato", flush=True)

    # Teniamo traccia dell'ultimo ID processato per ogni utente (in memoria — semplice e sufficiente)
    ultimo_id_calls: dict = {}
    ultimo_id_sms: dict = {}

    while not bot.is_closed():
        await asyncio.sleep(BOLLETTA_INTERVALLO_H * 3600)
        try:
            proprietari = await database.get_all_phone_owners()
            for uid in proprietari:
                since_c = ultimo_id_calls.get(uid, 0)
                since_s = ultimo_id_sms.get(uid, 0)
                n_calls, n_sms = await database.count_usage_since(uid, since_c, since_s)
                importo = n_calls * COSTO_CHIAMATA_BOLLETTA + n_sms * COSTO_SMS_BOLLETTA

                ultimo_id_calls[uid] = await database.get_max_call_id()
                ultimo_id_sms[uid]   = await database.get_max_sms_id()

                if importo <= 0:
                    continue

                bill_id = await database.add_bill(uid, importo)
                user_data = await database.get_user(uid)
                if user_data["cash"] >= importo:
                    await database.update_balance(uid, cash=user_data["cash"] - importo)
                    await database.pay_bill(bill_id)
                    esito = f"Addebitati automaticamente **${importo:,}** dai tuoi contanti."
                else:
                    esito = f"Non avevi abbastanza contanti! Bolletta di **${importo:,}** in sospeso — usa `/paga-bolletta`."

                try:
                    user = await bot.fetch_user(int(uid))
                    dm = discord.Embed(
                        title="📱 𝐁𝐨𝐥𝐥𝐞𝐭𝐭𝐚 𝐓𝐞𝐥𝐞𝐟𝐨𝐧𝐢𝐜𝐚",
                        description=f"📞 Chiamate: {n_calls}  •  💬 SMS: {n_sms}\n\n{esito}",
                        color=COLOR_PHONE,
                        timestamp=discord.utils.utcnow()
                    )
                    dm.set_footer(text="🏙️ West Coast RP '93 — Telefono")
                    await user.send(embed=dm)
                except Exception:
                    pass
        except Exception as e:
            print(f"❌ Errore task bolletta: {e}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SETUP COMANDI
# ══════════════════════════════════════════════════════════════════════════════
def setup_phone_commands(bot: commands.Bot):

    # ── /telefono ────────────────────────────────────────────────────────────
    @bot.tree.command(name="telefono", description="Apri il tuo telefono")
    async def telefono(interaction: discord.Interaction):
        phone = await _richiedi_telefono(interaction)
        if not phone:
            return
        menu = TelefonoMenuView(bot, str(interaction.user.id))
        embed = await menu._build_home_embed()
        await interaction.response.send_message(embed=embed, view=menu, ephemeral=True)

    # ── /vendi-telefono ──────────────────────────────────────────────────────
    @bot.tree.command(name="vendi-telefono", description="[Market] Vendi un telefono a un cliente")
    @app_commands.describe(utente="Il cliente a cui vendere il telefono", id_psn="ID PSN del cliente (diventerà il numero)")
    async def vendi_telefono(interaction: discord.Interaction, utente: discord.Member, id_psn: str):
        if not isinstance(interaction.user, discord.Member) or \
           not any(r.id == MARKET_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("❌ Solo il Market può vendere telefoni!", ephemeral=True)
            return
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi vendere un telefono a un bot.", ephemeral=True)
            return

        esistente = await database.get_phone(str(utente.id))
        if esistente:
            await interaction.response.send_message(
                f"❌ {utente.mention} possiede già un telefono (`{esistente['numero']}`).", ephemeral=True
            )
            return

        numero = f"+1 {id_psn.strip()}"
        if await database.get_phone_by_number(numero):
            await interaction.response.send_message(f"❌ Il numero **{numero}** è già in uso da un altro cliente.", ephemeral=True)
            return

        ok = await database.create_phone(str(utente.id), numero)
        if not ok:
            await interaction.response.send_message("❌ Errore durante la creazione del telefono.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📱 𝐓𝐞𝐥𝐞𝐟𝐨𝐧𝐨 𝐕𝐞𝐧𝐝𝐮𝐭𝐨",
            color=COLOR_PHONE,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Cliente", value=utente.mention, inline=True)
        embed.add_field(name="📞 Numero",  value=f"`{numero}`",  inline=True)
        embed.add_field(name="🏪 Venduto da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Market")
        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                title="📱 Hai ricevuto un telefono!",
                description=f"Il tuo nuovo numero è **`{numero}`**.\nUsa `/telefono` per aprirlo.",
                color=COLOR_PHONE
            )
            dm.set_footer(text="🏙️ West Coast RP '93 — Market")
            await utente.send(embed=dm)
        except Exception:
            pass

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="📱 LOG — Telefono Venduto", color=COLOR_PHONE, timestamp=discord.utils.utcnow())
                log.add_field(name="🏪 Venditore", value=interaction.user.mention, inline=True)
                log.add_field(name="👤 Cliente",   value=utente.mention,           inline=True)
                log.add_field(name="📞 Numero",    value=numero,                   inline=True)
                await ch.send(embed=log)
        except Exception:
            pass

    # ── /paga-bolletta ───────────────────────────────────────────────────────
    @bot.tree.command(name="paga-bolletta", description="Paga le bollette telefoniche in sospeso")
    async def paga_bolletta(interaction: discord.Interaction):
        uid = str(interaction.user.id)
        bollette = await database.get_unpaid_bills(uid)
        if not bollette:
            await interaction.response.send_message("✅ Non hai bollette in sospeso!", ephemeral=True)
            return

        totale = sum(b["importo"] for b in bollette)
        user = await database.get_user(uid)
        if user["cash"] < totale:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti.\nTotale bollette: **${totale:,}** — Tuoi: **${user['cash']:,}**", ephemeral=True
            )
            return

        await database.update_balance(uid, cash=user["cash"] - totale)
        for b in bollette:
            await database.pay_bill(b["id"])

        embed = discord.Embed(
            title="✅ 𝐁𝐨𝐥𝐥𝐞𝐭𝐭𝐚 𝐒𝐚𝐥𝐝𝐚𝐭𝐚",
            description=f"Hai pagato **${totale:,}** di bollette telefoniche.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🏙️ West Coast RP '93 — Telefono")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /fax ─────────────────────────────────────────────────────────────────
    @bot.tree.command(name="fax", description="[Ente Pubblico] Invia un fax a un altro ente")
    @app_commands.describe(
        mittente="Il tuo ente (deve corrispondere al tuo ruolo)",
        destinatario="L'ente destinatario",
        contenuto="Contenuto del fax"
    )
    @app_commands.choices(mittente=[app_commands.Choice(name=f"{c['emoji']} {n}", value=n) for n, c in ENTI_FAX.items()])
    @app_commands.choices(destinatario=[app_commands.Choice(name=f"{c['emoji']} {n}", value=n) for n, c in ENTI_FAX.items()])
    async def fax(interaction: discord.Interaction, mittente: str, destinatario: str, contenuto: str):
        cfg_mittente = ENTI_FAX[mittente]
        if not isinstance(interaction.user, discord.Member) or \
           not any(r.id == cfg_mittente["ruolo"] for r in interaction.user.roles):
            await interaction.response.send_message(f"❌ Non hai il ruolo per inviare fax a nome di **{mittente}**.", ephemeral=True)
            return
        if mittente == destinatario:
            await interaction.response.send_message("❌ Non puoi inviare un fax a te stesso.", ephemeral=True)
            return

        cfg_dest = ENTI_FAX[destinatario]
        embed = discord.Embed(
            title=f"📠 𝐅𝐀𝐗 — {cfg_mittente['emoji']} {mittente} → {cfg_dest['emoji']} {destinatario}",
            description=contenuto,
            color=COLOR_PHONE,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="✍️ Inviato da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Rete Fax Enti Pubblici")

        await interaction.response.send_message(embed=embed)

        if cfg_dest["canale"]:
            ch = bot.get_channel(cfg_dest["canale"])
            if ch and ch.id != interaction.channel_id:
                await ch.send(embed=embed)
