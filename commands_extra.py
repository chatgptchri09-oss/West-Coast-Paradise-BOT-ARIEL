import discord
from discord import app_commands
from discord.ext import commands
import random
import database
from constants import (
    LOG_CHANNEL_ID, BANK_CHANNEL_ID, BANCHIERE_ROLE_ID, DOTTORE_ROLE_ID,
    COMPANY_ROLES, has_staff, has_sceriffo
)

# ⚠️ Canali da confermare — al momento uso LOG_CHANNEL_ID come fallback.
#     Mandami gli ID reali se vuoi canali dedicati per questi registri.
CANALE_MANDATI    = 1531189272814686401   # Canale pubblico mandati di cattura
CANALE_PROVE      = 1531189106393092197   # Armadietto prove FDO
CANALE_FURTI      = 1531189311502815383   # Segnalazioni furto veicolo

TASSO_INTERESSE = 0.10   # 10% di interesse sui prestiti
PRESTITO_MASSIMO = 50000


def setup_extra_commands(bot: commands.Bot):

    # ════════════════════════════════════════════════════════════════════════
    #  /lavoro-lista
    # ════════════════════════════════════════════════════════════════════════
   
    # ════════════════════════════════════════════════════════════════════════
    #  /tassametro
    # ════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="tassametro", description="Fai pagare una corsa in taxi a un passeggero")
    @app_commands.describe(passeggero="Il passeggero che deve pagare la corsa")
    async def tassametro(interaction: discord.Interaction, passeggero: discord.Member):
        if passeggero.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi farti pagare la corsa da solo.", ephemeral=True)
            return
        if passeggero.bot:
            await interaction.response.send_message("❌ Non puoi far pagare un bot.", ephemeral=True)
            return

        tariffa = random.randint(50, 300)
        pass_data = await database.get_user(str(passeggero.id))
        if pass_data["cash"] < tariffa:
            await interaction.response.send_message(
                f"❌ {passeggero.display_name} non ha abbastanza contanti per la corsa (${tariffa:,}).", ephemeral=True
            )
            return

        driver_data = await database.get_user(str(interaction.user.id))
        await database.update_balance(str(passeggero.id), cash=pass_data["cash"] - tariffa)
        await database.update_balance(str(interaction.user.id), cash=driver_data["cash"] + tariffa)

        embed = discord.Embed(
            title="🚕 𝐂𝐨𝐫𝐬𝐚 𝐓𝐚𝐱𝐢 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐚𝐭𝐚",
            color=discord.Color(0xFFD700),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🚕 Autista",    value=interaction.user.mention, inline=True)
        embed.add_field(name="🧍 Passeggero", value=passeggero.mention,       inline=True)
        embed.add_field(name="💵 Tariffa",    value=f"${tariffa:,}",          inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Taxi")
        await interaction.response.send_message(embed=embed)

    # ════════════════════════════════════════════════════════════════════════
    #  /scommessa
    # ════════════════════════════════════════════════════════════════════════
    class ScommessaView(discord.ui.View):
        def __init__(self, sfidante: discord.Member, sfidato: discord.Member, importo: int):
            super().__init__(timeout=120)
            self.sfidante = sfidante
            self.sfidato  = sfidato
            self.importo  = importo
            self.risolta  = False

        @discord.ui.button(label="✅ Accetta scommessa", style=discord.ButtonStyle.green)
        async def accetta(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.sfidato.id:
                await interaction.response.send_message("❌ Solo lo sfidato può accettare questa scommessa.", ephemeral=True)
                return
            if self.risolta:
                await interaction.response.send_message("❌ Questa scommessa è già stata risolta.", ephemeral=True)
                return

            sfidante_data = await database.get_user(str(self.sfidante.id))
            sfidato_data  = await database.get_user(str(self.sfidato.id))
            if sfidante_data["cash"] < self.importo:
                await interaction.response.send_message(f"❌ {self.sfidante.mention} non ha più abbastanza contanti.", ephemeral=True)
                return
            if sfidato_data["cash"] < self.importo:
                await interaction.response.send_message("❌ Non hai abbastanza contanti per accettare.", ephemeral=True)
                return

            self.risolta = True
            for c in self.children:
                c.disabled = True

            vincitore = random.choice([self.sfidante, self.sfidato])
            perdente  = self.sfidato if vincitore.id == self.sfidante.id else self.sfidante

            vinc_data = await database.get_user(str(vincitore.id))
            perd_data = await database.get_user(str(perdente.id))
            await database.update_balance(str(vincitore.id), cash=vinc_data["cash"] + self.importo)
            await database.update_balance(str(perdente.id), cash=perd_data["cash"] - self.importo)

            embed = discord.Embed(
                title="🎲 𝐒𝐂𝐎𝐌𝐌𝐄𝐒𝐒𝐀 𝐑𝐈𝐒𝐎𝐋𝐓𝐀",
                description=f"🏆 **{vincitore.display_name}** vince **${self.importo:,}** da {perdente.mention}!",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="🏙️ West Coast RP '93 — Scommessa")
            await interaction.response.edit_message(embed=embed, view=self)

            try:
                ch = interaction.client.get_channel(LOG_CHANNEL_ID)
                if ch:
                    log = discord.Embed(title="🎲 LOG — Scommessa", color=discord.Color.gold(), timestamp=discord.utils.utcnow())
                    log.add_field(name="🏆 Vincitore", value=vincitore.mention, inline=True)
                    log.add_field(name="💸 Perdente",  value=perdente.mention,  inline=True)
                    log.add_field(name="💰 Importo",   value=f"${self.importo:,}", inline=True)
                    await ch.send(embed=log)
            except Exception:
                pass

        @discord.ui.button(label="❌ Rifiuta", style=discord.ButtonStyle.red)
        async def rifiuta(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.sfidato.id:
                await interaction.response.send_message("❌ Solo lo sfidato può rifiutare questa scommessa.", ephemeral=True)
                return
            self.risolta = True
            for c in self.children:
                c.disabled = True
            await interaction.response.edit_message(
                content=f"❌ {self.sfidato.mention} ha rifiutato la scommessa.", embed=None, view=self
            )

    @bot.tree.command(name="scommessa", description="Sfida un altro giocatore a una scommessa in denaro (50/50)")
    @app_commands.describe(sfidato="Il giocatore da sfidare", importo="Importo in $ della scommessa")
    async def scommessa(interaction: discord.Interaction, sfidato: discord.Member, importo: int):
        if sfidato.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi sfidare te stesso.", ephemeral=True)
            return
        if sfidato.bot:
            await interaction.response.send_message("❌ Non puoi sfidare un bot.", ephemeral=True)
            return
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return

        sfidante_data = await database.get_user(str(interaction.user.id))
        if sfidante_data["cash"] < importo:
            await interaction.response.send_message(f"❌ Non hai **${importo:,}** in contanti.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎲 𝐍𝐔𝐎𝐕𝐀 𝐒𝐂𝐎𝐌𝐌𝐄𝐒𝐒𝐀",
            description=(
                f"{interaction.user.mention} sfida {sfidato.mention} a una scommessa da **${importo:,}**!\n\n"
                f"🪙 50/50 — vince chi ha più fortuna."
            ),
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🏙️ West Coast RP '93 — Scommessa | In attesa di risposta")
        await interaction.response.send_message(
            content=sfidato.mention, embed=embed, view=ScommessaView(interaction.user, sfidato, importo)
        )

    # ════════════════════════════════════════════════════════════════════════
    #  /prestito-richiedi | /prestito-paga | /prestito-stato
    # ════════════════════════════════════════════════════════════════════════
    class PrestitoConfirmView(discord.ui.View):
        def __init__(self, loan_id: int, richiedente: discord.Member, importo: int, totale_da_pagare: int):
            super().__init__(timeout=600)
            self.loan_id          = loan_id
            self.richiedente      = richiedente
            self.importo          = importo
            self.totale_da_pagare = totale_da_pagare

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if not isinstance(interaction.user, discord.Member):
                return False
            if not any(r.id == BANCHIERE_ROLE_ID for r in interaction.user.roles):
                await interaction.response.send_message("❌ Solo il **Banchiere** può gestire questa richiesta.", ephemeral=True)
                return False
            return True

        @discord.ui.button(label="✅ Approva", style=discord.ButtonStyle.green)
        async def approva(self, interaction: discord.Interaction, button: discord.ui.Button):
            await database.update_loan_status(self.loan_id, "attivo", str(interaction.user.id))
            user = await database.get_user(str(self.richiedente.id))
            await database.update_balance(str(self.richiedente.id), cash=user["cash"] + self.importo)

            for c in self.children:
                c.disabled = True
            await interaction.response.edit_message(
                content=f"✅ **Prestito approvato da {interaction.user.display_name}**", view=self
            )
            try:
                dm = discord.Embed(
                    title="🏦 𝐏𝐫𝐞𝐬𝐭𝐢𝐭𝐨 𝐀𝐩𝐩𝐫𝐨𝐯𝐚𝐭𝐨",
                    description=(
                        f"Hai ricevuto **${self.importo:,}** in contanti.\n"
                        f"Dovrai restituire **${self.totale_da_pagare:,}** (interesse {int(TASSO_INTERESSE*100)}%).\n\n"
                        f"Usa `/prestito-paga` per saldare a rate."
                    ),
                    color=discord.Color.green()
                )
                dm.set_footer(text="🏙️ West Coast RP '93 — Palomino Bank")
                await self.richiedente.send(embed=dm)
            except Exception:
                pass

        @discord.ui.button(label="❌ Rifiuta", style=discord.ButtonStyle.red)
        async def rifiuta(self, interaction: discord.Interaction, button: discord.ui.Button):
            await database.update_loan_status(self.loan_id, "rifiutato", str(interaction.user.id))
            for c in self.children:
                c.disabled = True
            await interaction.response.edit_message(
                content=f"❌ **Prestito rifiutato da {interaction.user.display_name}**", view=self
            )
            try:
                dm = discord.Embed(
                    title="🏦 𝐏𝐫𝐞𝐬𝐭𝐢𝐭𝐨 𝐑𝐢𝐟𝐢𝐮𝐭𝐚𝐭𝐨",
                    description=f"La tua richiesta di prestito da **${self.importo:,}** è stata rifiutata.",
                    color=discord.Color.red()
                )
                dm.set_footer(text="🏙️ West Coast RP '93 — Palomino Bank")
                await self.richiedente.send(embed=dm)
            except Exception:
                pass

    @bot.tree.command(name="prestito-richiedi", description="Richiedi un prestito alla banca (interesse 10%)")
    @app_commands.describe(importo=f"Importo richiesto (max ${PRESTITO_MASSIMO:,})")
    async def prestito_richiedi(interaction: discord.Interaction, importo: int):
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return
        if importo > PRESTITO_MASSIMO:
            await interaction.response.send_message(f"❌ Il prestito massimo concedibile è **${PRESTITO_MASSIMO:,}**.", ephemeral=True)
            return

        uid = str(interaction.user.id)
        if await database.get_pending_loan(uid):
            await interaction.response.send_message("❌ Hai già una richiesta di prestito in attesa di approvazione.", ephemeral=True)
            return
        if await database.get_active_loan(uid):
            await interaction.response.send_message("❌ Hai già un prestito attivo. Saldalo prima di richiederne un altro.", ephemeral=True)
            return

        if interaction.guild is None:
            await interaction.response.send_message("❌ Questo comando funziona solo nel server.", ephemeral=True)
            return
        bank_ch = interaction.guild.get_channel(BANK_CHANNEL_ID)
        if bank_ch is None:
            await interaction.response.send_message("❌ Canale banca non trovato. Contatta lo Staff.", ephemeral=True)
            return

        totale_da_pagare = round(importo * (1 + TASSO_INTERESSE))
        loan_id = await database.add_loan_request(uid, importo, totale_da_pagare)

        embed = discord.Embed(
            title="🏦 𝐑𝐢𝐜𝐡𝐢𝐞𝐬𝐭𝐚 𝐏𝐫𝐞𝐬𝐭𝐢𝐭𝐨",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="👤 Richiedente",     value=interaction.user.mention,  inline=True)
        embed.add_field(name="💵 Importo",          value=f"${importo:,}",          inline=True)
        embed.add_field(name="📈 Interesse",        value=f"{int(TASSO_INTERESSE*100)}%", inline=True)
        embed.add_field(name="💰 Totale da restituire", value=f"${totale_da_pagare:,}", inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Solo il Banchiere può approvare")

        await bank_ch.send(
            content=f"<@&{BANCHIERE_ROLE_ID}> — Nuova richiesta di prestito da {interaction.user.mention}",
            embed=embed,
            view=PrestitoConfirmView(loan_id, interaction.user, importo, totale_da_pagare)
        )
        await interaction.response.send_message(
            f"✅ Richiesta di prestito da **${importo:,}** inviata al Banchiere.", ephemeral=True
        )

    @bot.tree.command(name="prestito-paga", description="Salda (in parte o del tutto) il tuo prestito attivo")
    @app_commands.describe(importo="Importo da versare")
    async def prestito_paga(interaction: discord.Interaction, importo: int):
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return

        uid  = str(interaction.user.id)
        loan = await database.get_active_loan(uid)
        if not loan:
            await interaction.response.send_message("❌ Non hai nessun prestito attivo.", ephemeral=True)
            return

        residuo = loan["total_due"] - loan["paid_amount"]
        importo = min(importo, residuo)

        user = await database.get_user(uid)
        if user["cash"] < importo:
            await interaction.response.send_message(f"❌ Contanti insufficienti. Disponibile: **${user['cash']:,}**", ephemeral=True)
            return

        await database.update_balance(uid, cash=user["cash"] - importo)
        loan_aggiornato = await database.pay_loan(loan["id"], importo)
        nuovo_residuo = loan_aggiornato["total_due"] - loan_aggiornato["paid_amount"]

        embed = discord.Embed(
            title="🏦 𝐑𝐚𝐭𝐚 𝐏𝐚𝐠𝐚𝐭𝐚",
            color=discord.Color.green() if nuovo_residuo == 0 else discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="💵 Versato",  value=f"${importo:,}", inline=True)
        embed.add_field(name="📉 Residuo",  value=f"${nuovo_residuo:,}", inline=True)
        if nuovo_residuo == 0:
            embed.add_field(name="✅ Stato", value="**Prestito saldato completamente!**", inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — Palomino Bank")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="prestito-stato", description="Controlla lo stato del tuo prestito")
    async def prestito_stato(interaction: discord.Interaction):
        uid = str(interaction.user.id)
        loan = await database.get_active_loan(uid) or await database.get_pending_loan(uid)
        if not loan:
            await interaction.response.send_message("✅ Non hai nessun prestito attivo o in attesa.", ephemeral=True)
            return

        residuo = loan["total_due"] - loan["paid_amount"]
        stato_label = {"in_attesa": "⏳ In attesa di approvazione", "attivo": "🟢 Attivo"}.get(loan["status"], loan["status"])

        embed = discord.Embed(title="🏦 𝐒𝐭𝐚𝐭𝐨 𝐏𝐫𝐞𝐬𝐭𝐢𝐭𝐨", color=discord.Color(0x1E90FF), timestamp=discord.utils.utcnow())
        embed.add_field(name="📋 Stato",    value=stato_label,             inline=True)
        embed.add_field(name="💵 Importo",  value=f"${loan['amount']:,}",  inline=True)
        embed.add_field(name="💰 Da restituire", value=f"${loan['total_due']:,}", inline=True)
        embed.add_field(name="✅ Già pagato", value=f"${loan['paid_amount']:,}", inline=True)
        embed.add_field(name="📉 Residuo",  value=f"${residuo:,}",         inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Palomino Bank")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    #  /rivendi-veicolo
    # ════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="rivendi-veicolo", description="Rivendi un tuo veicolo a un altro giocatore, trasferendo il libretto")
    @app_commands.describe(targa="La targa del veicolo da rivendere", acquirente="Il giocatore che compra", prezzo="Prezzo concordato in $")
    async def rivendi_veicolo(interaction: discord.Interaction, targa: str, acquirente: discord.Member, prezzo: int):
        if acquirente.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi vendertelo da solo.", ephemeral=True)
            return
        if acquirente.bot:
            await interaction.response.send_message("❌ Non puoi vendere un veicolo a un bot.", ephemeral=True)
            return
        if prezzo < 0:
            await interaction.response.send_message("❌ Prezzo non valido.", ephemeral=True)
            return

        targa_val = targa.strip().upper()
        vehicle = await database.get_vehicle_by_plate(targa_val)
        if not vehicle:
            await interaction.response.send_message(f"❌ Nessun veicolo trovato con la targa **{targa_val}**.", ephemeral=True)
            return
        if vehicle["user_id"] != str(interaction.user.id):
            await interaction.response.send_message("❌ Questo veicolo non è registrato a tuo nome.", ephemeral=True)
            return
        if vehicle.get("rubato"):
            await interaction.response.send_message("❌ Non puoi rivendere un veicolo segnalato come rubato.", ephemeral=True)
            return

        if prezzo > 0:
            buyer_data = await database.get_user(str(acquirente.id))
            if buyer_data["cash"] < prezzo:
                await interaction.response.send_message(f"❌ {acquirente.display_name} non ha abbastanza contanti.", ephemeral=True)
                return
            seller_data = await database.get_user(str(interaction.user.id))
            await database.update_balance(str(acquirente.id), cash=buyer_data["cash"] - prezzo)
            await database.update_balance(str(interaction.user.id), cash=seller_data["cash"] + prezzo)

        parti_nome = None
        try:
            doc = await database.get_document(str(acquirente.id))
            nome_new    = doc["nome"] if doc else acquirente.display_name
            cognome_new = doc["cognome"] if doc else ""
        except Exception:
            nome_new, cognome_new = acquirente.display_name, ""

        await database.transfer_vehicle(targa_val, str(acquirente.id), nome_new, cognome_new)

        embed = discord.Embed(
            title="🚗 𝐕𝐄𝐈𝐂𝐎𝐋𝐎 𝐑𝐈𝐕𝐄𝐍𝐃𝐔𝐓𝐎",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🚙 Veicolo",     value=f"{vehicle.get('vehicle_brand','')} {vehicle['vehicle_model']}".strip(), inline=True)
        embed.add_field(name="🔖 Targa",       value=targa_val,             inline=True)
        embed.add_field(name="💰 Prezzo",      value=f"${prezzo:,}",       inline=True)
        embed.add_field(name="👤 Venditore",   value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 Acquirente",  value=acquirente.mention,   inline=True)
        embed.set_footer(text="🏙️ West Coast RP '93 — Concessionario")
        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                title="🚗 Hai acquistato un veicolo!",
                description=f"Hai ricevuto il libretto di **{vehicle.get('vehicle_brand','')} {vehicle['vehicle_model']}** (targa `{targa_val}`) da {interaction.user.mention}.",
                color=discord.Color(0x1E90FF)
            )
            await acquirente.send(embed=dm)
        except Exception:
            pass

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="🚗 LOG — Veicolo Rivenduto", color=discord.Color(0x1E90FF), timestamp=discord.utils.utcnow())
                log.add_field(name="🔖 Targa",      value=targa_val,             inline=True)
                log.add_field(name="👤 Venditore",  value=interaction.user.mention, inline=True)
                log.add_field(name="🎯 Acquirente", value=acquirente.mention,   inline=True)
                await ch.send(embed=log)
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════════════
    #  /furto-veicolo
    # ════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="furto-veicolo", description="Segnala il furto del tuo veicolo alle FDO")
    @app_commands.describe(targa="La targa del veicolo rubato", ultima_posizione="Dove l'hai visto l'ultima volta (opzionale)")
    async def furto_veicolo(interaction: discord.Interaction, targa: str, ultima_posizione: str = ""):
        targa_val = targa.strip().upper()
        vehicle = await database.get_vehicle_by_plate(targa_val)
        if not vehicle:
            await interaction.response.send_message(f"❌ Nessun veicolo trovato con la targa **{targa_val}**.", ephemeral=True)
            return
        if vehicle["user_id"] != str(interaction.user.id) and not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Puoi segnalare come rubato solo un veicolo registrato a tuo nome.", ephemeral=True)
            return

        await database.set_vehicle_stolen(targa_val, True, ultima_posizione)

        embed = discord.Embed(
            title="🚨 𝐒𝐄𝐆𝐍𝐀𝐋𝐀𝐙𝐈𝐎𝐍𝐄 𝐅𝐔𝐑𝐓𝐎 𝐕𝐄𝐈𝐂𝐎𝐋𝐎",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🚙 Veicolo",  value=f"{vehicle.get('vehicle_brand','')} {vehicle['vehicle_model']}".strip(), inline=True)
        embed.add_field(name="🔖 Targa",    value=targa_val,              inline=True)
        embed.add_field(name="👤 Denunciato da", value=interaction.user.mention, inline=True)
        if ultima_posizione:
            embed.add_field(name="📍 Ultima posizione nota", value=ultima_posizione, inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — FDO / LSPD")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(CANALE_FURTI)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════════════
    #  /traccia-veicolo
    # ════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="traccia-veicolo", description="[FDO] Controlla se un veicolo è segnalato rubato e la sua ultima posizione")
    @app_commands.describe(targa="La targa del veicolo da tracciare")
    async def traccia_veicolo(interaction: discord.Interaction, targa: str):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo le FDO possono usare questo comando.", ephemeral=True)
            return

        targa_val = targa.strip().upper()
        vehicle = await database.get_vehicle_by_plate(targa_val)
        if not vehicle:
            await interaction.response.send_message(f"❌ Nessun veicolo trovato con la targa **{targa_val}**.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📡 TRACCIAMENTO: {targa_val}",
            color=discord.Color.red() if vehicle.get("rubato") else discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🚙 Veicolo",      value=f"{vehicle.get('vehicle_brand','')} {vehicle['vehicle_model']}".strip(), inline=True)
        embed.add_field(name="👤 Proprietario", value=f"<@{vehicle['user_id']}>", inline=True)
        embed.add_field(name="🚨 Stato",        value="🔴 SEGNALATO RUBATO" if vehicle.get("rubato") else "✅ Regolare", inline=False)
        if vehicle.get("ultima_posizione"):
            embed.add_field(name="📍 Ultima posizione nota", value=vehicle["ultima_posizione"], inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — FDO / LSPD")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    #  /mandato-cattura
    # ════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="mandato-cattura", description="[FDO] Emetti un mandato di cattura pubblico su un sospettato")
    @app_commands.describe(sospettato="La persona ricercata", motivo="Motivo del mandato")
    async def mandato_cattura(interaction: discord.Interaction, sospettato: discord.Member, motivo: str):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo le FDO possono emettere mandati di cattura.", ephemeral=True)
            return
        if sospettato.bot:
            await interaction.response.send_message("❌ Non puoi emettere un mandato su un bot.", ephemeral=True)
            return

        await database.add_warrant(str(sospettato.id), motivo, str(interaction.user.id))

        embed = discord.Embed(
            title="🚨 𝐌𝐀𝐍𝐃𝐀𝐓𝐎 𝐃𝐈 𝐂𝐀𝐓𝐓𝐔𝐑𝐀",
            description=f"{sospettato.mention} è **ufficialmente ricercato** dalle Forze dell'Ordine.",
            color=discord.Color.dark_red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=sospettato.display_avatar.url)
        embed.add_field(name="🧑 Ricercato", value=sospettato.mention,        inline=True)
        embed.add_field(name="👮 Emesso da", value=interaction.user.mention,  inline=True)
        embed.add_field(name="📋 Motivo",    value=motivo,                    inline=False)
        embed.set_footer(text="🏙️ West Coast RP '93 — FDO / LSPD | Chiunque avvisti il ricercato lo segnali")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(CANALE_MANDATI)
            if ch and ch.id != interaction.channel_id:
                await ch.send(embed=embed)
        except Exception:
            pass

        try:
            dm = discord.Embed(
                title="🚨 Hai un mandato di cattura a tuo carico!",
                description=f"**Motivo:** {motivo}\n\nCostituisciti o rischi conseguenze peggiori.",
                color=discord.Color.dark_red()
            )
            await sospettato.send(embed=dm)
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════════════
    #  /deposito-prove
    # ════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="deposito-prove", description="[FDO] Registra una prova nell'armadietto prove")
    @app_commands.describe(titolo="Titolo/riferimento del caso", descrizione="Descrizione della prova", foto="Foto della prova (opzionale)")
    async def deposito_prove(interaction: discord.Interaction, titolo: str, descrizione: str, foto: discord.Attachment = None):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo le FDO possono usare questo comando.", ephemeral=True)
            return

        foto_url = None
        if foto:
            if not foto.content_type or not foto.content_type.startswith("image/"):
                await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True)
                return
            foto_url = foto.url

        prova_id = await database.add_evidence(titolo, descrizione, foto_url, str(interaction.user.id))

        embed = discord.Embed(
            title=f"🗃️ 𝐏𝐫𝐨𝐯𝐚 𝐑𝐞𝐠𝐢𝐬𝐭𝐫𝐚𝐭𝐚 — #{prova_id}",
            color=discord.Color(0x1E90FF),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📁 Titolo/Caso", value=titolo, inline=False)
        embed.add_field(name="📋 Descrizione", value=descrizione, inline=False)
        embed.add_field(name="👮 Registrata da", value=interaction.user.mention, inline=True)
        if foto_url:
            embed.set_image(url=foto_url)
        embed.set_footer(text="🏙️ West Coast RP '93 — Armadietto Prove FDO")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(CANALE_PROVE)
            if ch and ch.id != interaction.channel_id:
                await ch.send(embed=embed)
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════════════
    #  /curami
    # ════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="cura", description="[Servizi Medici] Cura un paziente ferito ripristinandolo completamente")
    @app_commands.describe(paziente="Il paziente da curare")
    async def curami(interaction: discord.Interaction, paziente: discord.Member):
        if not isinstance(interaction.user, discord.Member) or \
           not any(r.id == DOTTORE_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("❌ Solo i Servizi Medici possono usare questo comando.", ephemeral=True)
            return

        await database.update_hunger_thirst(str(paziente.id), hunger=100, thirst=100)
        await database.set_ferito(str(paziente.id), False)

        embed = discord.Embed(
            title="🩺 𝐏𝐚𝐳𝐢𝐞𝐧𝐭𝐞 𝐂𝐮𝐫𝐚𝐭𝐨",
            description=f"{paziente.mention} è stato curato da {interaction.user.mention} ed è tornato in perfetta forma.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🏙️ West Coast RP '93 — Servizi Medici")
        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                title="🩺 Sei stato curato!",
                description=f"Il dottore **{interaction.user.display_name}** ti ha curato. Fame e sete sono state ripristinate al 100%.",
                color=discord.Color.green()
            )
            await paziente.send(embed=dm)
        except Exception:
            pass
