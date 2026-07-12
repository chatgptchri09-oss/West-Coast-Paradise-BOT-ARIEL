import discord

# ══════════════════════════════════════════════
#  COSTANTI — RDR2 RP BOT
# ══════════════════════════════════════════════

STAFF_ROLE_ID     = 1414738761207517214
FORZEDELLORDINE_ROLE_ID  = 1524525114526269470
DOTTORE_ROLE_ID   = 1525400195628662784
ARMERIA_ROLE_ID   = 1415092383250382858
CONCESSIONARIO_ROLE_ID    = 1415238213303406702
BAR_ROLE_ID    = 1525768396703141889
MARKET_ROLE_ID   = 1415242295153918123
CONTRABBANDO_DOC_ID   = 1525816899987046491
STATO_ROLE_ID     = 1524525114526269470
DILIGENZA_ROLE_ID = [1421007310771191829, 1421007929301139626]
CHIAVE_ROLE_ID    = 1414735564632231988
BANCHIERE_ROLE_ID    = 1431387710194454639

LOG_CHANNEL_ID    = 1415297578022604850
BANK_CHANNEL_ID   = 1525863299714121908
DATABASE_NAME     = "rdr2_bot.db"

# Gruppi
STAFF_ROLES    = [STAFF_ROLE_ID, CHIAVE_ROLE_ID]
FORZEDELLORDINE_ROLES = [FORZEDELLORDINE_ROLE_ID, STATO_ROLE_ID]

COMPANY_ROLES = {
    "Sceriffo":     SCERIFFO_ROLE_ID,
    "Dottore":      DOTTORE_ROLE_ID,
    "Armiere":      ARMIERE_ROLE_ID,
    "Stalla":       STALLA_ROLE_ID,
    "Saloon":       SALOON_ROLE_ID,
    "Emporio":      EMPORIO_ROLE_ID,
    "Contrabbando": CONTRABBANDO_ID,
    "Diligenza":    1421007310771191829,
    "Banchiere":    BANKER_ROLE_ID,
    "Distilleria":  DISTILL_ROLE_ID,
    "FightClub":    FIGHT_ROLE_ID,
    "Macelleria":   MACELLERIA_ROLE_ID,
}

# ── Helper permessi ───────────────────────────
def has_staff(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in STAFF_ROLES for r in interaction.user.roles)

def has_sceriffo(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in SCERIFFO_ROLES for r in interaction.user.roles)

def has_role_id(interaction, role_id) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    if isinstance(role_id, list):
        return any(r.id in role_id for r in interaction.user.roles)
    return any(r.id == role_id for r in interaction.user.roles)
