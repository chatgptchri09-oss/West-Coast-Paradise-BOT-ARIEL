import discord

# ══════════════════════════════════════════════
#  COSTANTI — WEST COAST RP BOT
# ══════════════════════════════════════════════

# ── Ruoli Staff ───────────────────────────────
STAFF_ROLE_ID      = 1414738761207517214
CHIAVE_ROLE_ID     = 1414735564632231988
DEVELOPER_ROLE_ID  = 1458161081024516242

# ── Forze dell'Ordine ─────────────────────────
FORZEDELLORDINE_ROLE_ID = 1524525114526269470
SHERIFF_ROLE_ID         = 1415093546549248040
FBI_ROLE_ID             = 1524527285406007296
STATO_ROLE_ID           = 1524525114526269470   # alias FDO per compatibilità

# ── Lavori / Fazioni ──────────────────────────
DOTTORE_ROLE_ID              = 1525400195628662784
ARMERIA_ROLE_ID              = 1415092383250382858
CONCESSIONARIO_ROLE_ID       = 1415238213303406702
BAR_ROLE_ID                  = 1525768396703141889   # Yellow Jack
MARKET_ROLE_ID               = 1415242295153918123   # Supermarket
CONTRABBANDO_DOC_ROLE_ID     = 1525816899987046491
MECCANICO_ROLE_ID            = 1415240071216500746   # Beeker Garage
PEGASUS_ROLE_ID              = 1415262517407645828
AGENZIA_IMMOBILIARE_ROLE_ID  = 1424381004944244828
NOTARIATO_ROLE_ID            = 1525728139802841181
COUNTY_DONUTS_ROLE_ID        = 1525770209749631156
COUNTY_IMPOUND_ROLE_ID       = 1525773129492988014

# ── Banca ─────────────────────────────────────
BANCA_ROLE_ID      = 1431387710194454639   # Palomino Bank
BANCHIERE_ROLE_ID  = 1431387710194454639   # alias per compatibilità

# ── Canali log aziende ────────────────────────
LOG_ARMERIA_CH         = 1424111403228205147
LOG_CONCESSIONARIO_CH  = 1424111522107490405
LOG_AGENZIA_CH         = 1528733707295264878
LOG_MECCANICO_CH       = 1527399514317783050
LOG_PEGASUS_CH         = 1527663873103106189
LOG_NOTARIATO_CH       = 1528783581693087834
LOG_YELLOWJACK_CH      = 1528783615486464100
LOG_COUNTYDONUTS_CH    = 1528783643462336765
LOG_COUNTYIMPOUND_CH   = 1528783671593533700
LOG_DOTTORE_CH         = 1529909257019855069

# ── Registri ───────────────────────────────────
REGISTRO_CERTIFICATI_MEDICI_CH = 1529920724905627698
REGISTRO_PORTODARMI_CH         = 1414764241692528691

# ── Canali ────────────────────────────────────
LOG_CHANNEL_ID   = 1479158931610931414
BANK_CHANNEL_ID  = 1525863299714121908
LIBRETTO_PERSONALE_CH  = 1414760642841411614
LIBRETTO_AZIENDALE_CH  = 1528733172651790396

# ── Database ──────────────────────────────────
DATABASE_NAME = "rdr2_bot.db"

# ── Gruppi ruoli ──────────────────────────────
STAFF_ROLES = [STAFF_ROLE_ID, CHIAVE_ROLE_ID, DEVELOPER_ROLE_ID]

FORZEDELLORDINE_ROLES = [
    FORZEDELLORDINE_ROLE_ID,
    SHERIFF_ROLE_ID,
    FBI_ROLE_ID,
    STATO_ROLE_ID,
]

COMPANY_ROLES = {
    "Forze dell'Ordine": FORZEDELLORDINE_ROLE_ID,
    "Sheriff":           SHERIFF_ROLE_ID,
    "FBI":               FBI_ROLE_ID,
    "Dottore":           DOTTORE_ROLE_ID,
    "Armeria":           ARMERIA_ROLE_ID,
    "Concessionario":    CONCESSIONARIO_ROLE_ID,
    "Bar":               BAR_ROLE_ID,
    "Market":            MARKET_ROLE_ID,
    "Contrabbando":      CONTRABBANDO_DOC_ROLE_ID,
    "Meccanico":         MECCANICO_ROLE_ID,
    "Pegasus":           PEGASUS_ROLE_ID,
    "Agenzia Imm.":      AGENZIA_IMMOBILIARE_ROLE_ID,
    "Banca":             BANCA_ROLE_ID,
    "Notariato":         NOTARIATO_ROLE_ID,
    "County Donuts":     COUNTY_DONUTS_ROLE_ID,
    "County Impound":    COUNTY_IMPOUND_ROLE_ID,
}

# ── Helper permessi ───────────────────────────
def has_staff(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in STAFF_ROLES for r in interaction.user.roles)


def has_sceriffo(interaction) -> bool:
    """Controlla se l'utente è nelle Forze dell'Ordine (FDO, Sheriff, FBI)."""
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in FORZEDELLORDINE_ROLES for r in interaction.user.roles)


def has_role_id(interaction, role_id) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    if isinstance(role_id, (list, tuple)):
        return any(r.id in role_id for r in interaction.user.roles)
    return any(r.id == role_id for r in interaction.user.roles)
