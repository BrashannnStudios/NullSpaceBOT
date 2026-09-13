import discord
import datetime
from discord.ext import commands
from database import get_db

EMOJI_OK = "<:Aceptar:1548485480964689970>"
EMOJI_ERROR = "<:DenegadoEmoji:1548485532256960543>"
EMOJI_WARN = "<:AvisoEmoji:1548485507468492831>"
EMOJI_BAN = "<:DenegadoEmoji:1548485532256960543>"
EMOJI_MUTE = "<:RelojArenaEmoji:1548485607477739571>"
EMOJI_INFO = "<:Lupaemoji:1548485565350019132>"
EMOJI_LOCK = "<:DenegadoEmoji:1548485532256960543>"
EMOJI_UNLOCK = "<:Aceptar:1548485480964689970>"
EMOJI_NOTE = "<:PlumaEmoji:1548485587093164162>"
EMOJI_TIME = "<:RelojEmoji:1548485628944064663>"


def parse_duration(text: str) -> datetime.timedelta:
    units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    unit = text[-1].lower()
    if unit not in units:
        raise ValueError("Formato inválido. Usá ej: 10m, 2h, 1d")
    value = int(text[:-1])
    return datetime.timedelta(**{units[unit]: value})


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- LOCK / UNLOCK ----------

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"{EMOJI_LOCK} Canal bloqueado.")

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"{EMOJI_UNLOCK} Canal desbloqueado.")

    # ---------- WARNS ----------

    @commands.command(name="warn")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Sin razón"):
        db = get_db()
        warn_doc = {
            "guild_id": ctx.guild.id,
            "user_id": member.id,
            "moderator_id": ctx.author.id,
            "reason": reason,
            "timestamp": datetime.datetime.utcnow(),
        }
        result = await db.warnings.insert_one(warn_doc)
        await ctx.send(f"{EMOJI_WARN} {member.mention} fue advertido. Razón: {reason} (ID: `{result.inserted_id}`)")
        try:
            await member.send(f"{EMOJI_WARN} Fuiste advertido en **{ctx.guild.name}**. Razón: {reason}")
        except discord.Forbidden:
            pass

    @commands.command(name="delwarn")
    @commands.has_permissions(moderate_members=True)
    async def delwarn(self, ctx: commands.Context, warn_id: str):
        from bson import ObjectId
        db = get_db()
        try:
            oid = ObjectId(warn_id)
        except Exception:
            await ctx.send(f"{EMOJI_ERROR} ID de warn inválido.")
            return
        result = await db.warnings.delete_one({"_id": oid, "guild_id": ctx.guild.id})
        if result.deleted_count:
            await ctx.send(f"{EMOJI_OK} Warn eliminado.")
        else:
            await ctx.send(f"{EMOJI_ERROR} No se encontró ese warn.")

    @commands.command(name="warnings")
    async def warnings_cmd(self, ctx: commands.Context, member: discord.Member):
        db = get_db()
        cursor = db.warnings.find({"guild_id": ctx.guild.id, "user_id": member.id})
        warns = await cursor.to_list(length=50)
        if not warns:
            await ctx.send(f"{member.mention} no tiene advertencias.")
            return
        embed = discord.Embed(title=f"Advertencias de {member}", color=0xFFA500)
        for w in warns:
            embed.add_field(
                name=f"ID: {w['_id']}",
                value=f"Razón: {w['reason']}\nModerador: <@{w['moderator_id']}>",
                inline=False,
            )
        await ctx.send(embed=embed)

    # ---------- NOTES ----------

    @commands.command(name="addnote")
    @commands.has_permissions(moderate_members=True)
    async def addnote(self, ctx: commands.Context, member: discord.Member, *, note: str):
        db = get_db()
        result = await db.notes.insert_one({
            "guild_id": ctx.guild.id,
            "user_id": member.id,
            "moderator_id": ctx.author.id,
            "note": note,
            "timestamp": datetime.datetime.utcnow(),
        })
        await ctx.send(f"{EMOJI_NOTE} Nota agregada a {member.mention} (ID: `{result.inserted_id}`)")

    @commands.command(name="removenote")
    @commands.has_permissions(moderate_members=True)
    async def removenote(self, ctx: commands.Context, note_id: str):
        from bson import ObjectId
        db = get_db()
        try:
            oid = ObjectId(note_id)
        except Exception:
            await ctx.send(f"{EMOJI_ERROR} ID de nota inválido.")
            return
        result = await db.notes.delete_one({"_id": oid, "guild_id": ctx.guild.id})
        if result.deleted_count:
            await ctx.send(f"{EMOJI_OK} Nota eliminada.")
        else:
            await ctx.send(f"{EMOJI_ERROR} No se encontró esa nota.")

    # ---------- BAN / TEMPBAN / UNBAN ----------

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Sin razón"):
        try:
            await member.send(f"{EMOJI_BAN} Fuiste baneado de **{ctx.guild.name}**. Razón: {reason}")
        except discord.Forbidden:
            pass
        await member.ban(reason=reason)
        await ctx.send(f"{EMOJI_BAN} {member} fue baneado. Razón: {reason}")

    @commands.command(name="tempban")
    @commands.has_permissions(ban_members=True)
    async def tempban(self, ctx: commands.Context, member: discord.Member, duration: str, *, reason: str = "Sin razón"):
        try:
            delta = parse_duration(duration)
        except ValueError as e:
            await ctx.send(f"{EMOJI_ERROR} {e}")
            return
        db = get_db()
        unban_at = datetime.datetime.utcnow() + delta
        await db.tempbans.insert_one({
            "guild_id": ctx.guild.id,
            "user_id": member.id,
            "unban_at": unban_at,
        })
        await member.ban(reason=f"Tempban: {reason}")
        await ctx.send(f"{EMOJI_MUTE} {member} baneado temporalmente por {duration}. Razón: {reason}")

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: int):
        user = discord.Object(id=user_id)
        try:
            await ctx.guild.unban(user)
            await ctx.send(f"{EMOJI_OK} Usuario `{user_id}` desbaneado.")
        except discord.NotFound:
            await ctx.send(f"{EMOJI_ERROR} Ese usuario no está baneado.")

    # ---------- MUTE / UNMUTE (timeout) ----------

    @commands.command(name="mute")
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, duration: str = "10m", *, reason: str = "Sin razón"):
        try:
            delta = parse_duration(duration)
        except ValueError as e:
            await ctx.send(f"{EMOJI_ERROR} {e}")
            return
        await member.timeout(delta, reason=reason)
        await ctx.send(f"{EMOJI_MUTE} {member.mention} muteado por {duration}. Razón: {reason}")

    @commands.command(name="unmute")
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        await member.timeout(None)
        await ctx.send(f"{EMOJI_OK} {member.mention} desmuteado.")

    # ---------- SLOWMODE ----------

    @commands.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int):
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(f"{EMOJI_OK} Slowmode configurado a {seconds}s.")

    # ---------- USERINFO ----------

    @commands.command(name="userinfo")
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=f"Información de {member}", color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Cuenta creada", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
        embed.add_field(name="Se unió", value=discord.utils.format_dt(member.joined_at, "R"), inline=True)
        roles = ", ".join(r.mention for r in member.roles if r != ctx.guild.default_role) or "Ninguno"
        embed.add_field(name="Roles", value=roles, inline=False)
        await ctx.send(embed=embed)

    # ---------- DM ----------

    @commands.command(name="dm")
    @commands.has_permissions(moderate_members=True)
    async def dm(self, ctx: commands.Context, member: discord.Member, *, mensaje: str):
        try:
            await member.send(f"{EMOJI_INFO} Mensaje del staff de **{ctx.guild.name}**:\n{mensaje}")
            await ctx.send(f"{EMOJI_OK} Mensaje enviado a {member.mention}.")
        except discord.Forbidden:
            await ctx.send(f"{EMOJI_ERROR} No se pudo enviar el DM (usuario con DMs cerrados).")

    # ---------- CMDS ----------

    @commands.command(name="cmds")
    async def cmds(self, ctx: commands.Context):
        embed = discord.Embed(
            title=f"{EMOJI_NOTE} Comandos de NullSpaceBOT",
            description="Prefijo: `?` (no distingue mayúsculas)",
            color=0x2F3136,
        )
        embed.add_field(
            name="Moderación",
            value=(
                "`?lock` `?unlock`\n"
                "`?ban` `?tempban` `?unban`\n"
                "`?mute` `?unmute`\n"
                "`?warn` `?warnings` `?delwarn`\n"
                "`?addnote` `?removenote`\n"
                "`?slowmode`"
            ),
            inline=True,
        )
        embed.add_field(
            name="Utilidad",
            value=(
                "`?dm`\n"
                "`?userinfo`\n"
                "`?cmds`"
            ),
            inline=True,
        )
        embed.add_field(
            name="Others",
            value="`/welcome-setup`",
            inline=False,
        )
        embed.set_footer(text="NullSpaceBOT")
        await ctx.send(embed=embed)

    # ---------- Manejo de errores local ----------

    async def cog_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{EMOJI_ERROR} No tenés permisos para usar este comando.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"{EMOJI_ERROR} No encontré a ese usuario.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"{EMOJI_ERROR} Faltan argumentos: `{error.param.name}`")
        else:
            await ctx.send(f"{EMOJI_ERROR} Ocurrió un error: {error}")
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
