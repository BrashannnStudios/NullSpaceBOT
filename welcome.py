import discord
from discord import app_commands
from discord.ext import commands
from database import get_db

EMOJI_CHANNEL = "<:RelojEmoji:1548485628944064663>"
EMOJI_MESSAGE = "<:PlumaEmoji:1548485587093164162>"
EMOJI_COLOR = "<:PlumaEmoji:1548485587093164162>"
EMOJI_IMAGE = "<:Lupaemoji:1548485565350019132>"
EMOJI_LINKS = "<:RelojArenaEmoji:1548485607477739571>"
EMOJI_RECOMMENDED = "<:AvisoEmoji:1548485507468492831>"
EMOJI_SAVE = "<:Aceptar:1548485480964689970>"
EMOJI_PREVIEW = "<:Lupaemoji:1548485565350019132>"


def default_config(guild_id: int):
    return {
        "guild_id": guild_id,
        "channel_id": None,
        "message": "¡Bienvenido/a {mention} a **{server}**! Ya somos **{member_count}** miembros.",
        "color": 0x2F3136,
        "image": None,
        "recommended_channels": [],
        "links": [],  # [{"label": str, "url": str}]
    }


async def get_config(guild_id: int):
    db = get_db()
    cfg = await db.welcome_config.find_one({"guild_id": guild_id})
    if not cfg:
        cfg = default_config(guild_id)
        await db.welcome_config.insert_one(cfg)
    return cfg


async def update_config(guild_id: int, data: dict):
    db = get_db()
    await db.welcome_config.update_one(
        {"guild_id": guild_id}, {"$set": data}, upsert=True
    )


def build_welcome_embed(cfg: dict, member: discord.Member):
    text = cfg["message"].format(
        mention=member.mention,
        user=member.name,
        server=member.guild.name,
        member_count=member.guild.member_count,
    )
    embed = discord.Embed(description=text, color=cfg.get("color", 0x2F3136))
    embed.set_author(name=member.guild.name, icon_url=member.guild.icon.url if member.guild.icon else None)
    if cfg.get("image"):
        embed.set_image(url=cfg["image"])
    if cfg.get("recommended_channels"):
        rec = "\n".join(f"<#{cid}>" for cid in cfg["recommended_channels"])
        embed.add_field(name=f"{EMOJI_RECOMMENDED} Canales recomendados", value=rec, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


def build_links_view(cfg: dict):
    if not cfg.get("links"):
        return None
    view = discord.ui.View(timeout=None)
    for link in cfg["links"]:
        view.add_item(discord.ui.Button(label=link["label"], url=link["url"], style=discord.ButtonStyle.link))
    return view


# ---------- Modales ----------

class MessageModal(discord.ui.Modal, title="Configurar mensaje de bienvenida"):
    def __init__(self, panel: "SetupPanel"):
        super().__init__()
        self.panel = panel
        self.mensaje = discord.ui.TextInput(
            label="Mensaje (usa {mention} {server} {member_count})",
            style=discord.TextStyle.paragraph,
            default=panel.cfg["message"],
            max_length=1000,
        )
        self.add_item(self.mensaje)

    async def on_submit(self, interaction: discord.Interaction):
        self.panel.cfg["message"] = str(self.mensaje.value)
        await update_config(interaction.guild.id, {"message": self.panel.cfg["message"]})
        await interaction.response.edit_message(embed=self.panel.build_panel_embed(), view=self.panel)


class ColorModal(discord.ui.Modal, title="Configurar color del embed"):
    def __init__(self, panel: "SetupPanel"):
        super().__init__()
        self.panel = panel
        self.color = discord.ui.TextInput(
            label="Color en HEX (ej: #2F3136)",
            default=f"#{panel.cfg['color']:06X}",
            max_length=7,
        )
        self.add_item(self.color)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = str(self.color.value).replace("#", "")
            color_int = int(value, 16)
        except ValueError:
            await interaction.response.send_message("❌ Color inválido, usá formato HEX.", ephemeral=True)
            return
        self.panel.cfg["color"] = color_int
        await update_config(interaction.guild.id, {"color": color_int})
        await interaction.response.edit_message(embed=self.panel.build_panel_embed(), view=self.panel)


class ImageModal(discord.ui.Modal, title="Configurar imagen/gif"):
    def __init__(self, panel: "SetupPanel"):
        super().__init__()
        self.panel = panel
        self.url = discord.ui.TextInput(
            label="URL de la imagen o gif",
            default=panel.cfg.get("image") or "",
            required=False,
            max_length=500,
        )
        self.add_item(self.url)

    async def on_submit(self, interaction: discord.Interaction):
        value = str(self.url.value).strip() or None
        self.panel.cfg["image"] = value
        await update_config(interaction.guild.id, {"image": value})
        await interaction.response.edit_message(embed=self.panel.build_panel_embed(), view=self.panel)


class LinkModal(discord.ui.Modal, title="Agregar link/botón"):
    def __init__(self, panel: "SetupPanel"):
        super().__init__()
        self.panel = panel
        self.label = discord.ui.TextInput(label="Texto del botón", max_length=80)
        self.url = discord.ui.TextInput(label="URL", max_length=300)
        self.add_item(self.label)
        self.add_item(self.url)

    async def on_submit(self, interaction: discord.Interaction):
        url = str(self.url.value)
        if not url.startswith("http"):
            await interaction.response.send_message("❌ La URL debe empezar con http/https.", ephemeral=True)
            return
        links = self.panel.cfg.get("links", [])
        if len(links) >= 5:
            await interaction.response.send_message("❌ Máximo 5 links.", ephemeral=True)
            return
        links.append({"label": str(self.label.value), "url": url})
        self.panel.cfg["links"] = links
        await update_config(interaction.guild.id, {"links": links})
        await interaction.response.edit_message(embed=self.panel.build_panel_embed(), view=self.panel)


# ---------- Selects ----------

class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, panel: "SetupPanel"):
        super().__init__(
            placeholder="Elegí el canal de bienvenidas",
            channel_types=[discord.ChannelType.text],
        )
        self.panel = panel

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        self.panel.cfg["channel_id"] = channel.id
        await update_config(interaction.guild.id, {"channel_id": channel.id})
        await interaction.response.edit_message(embed=self.panel.build_panel_embed(), view=self.panel)


class RecommendedChannelsSelect(discord.ui.ChannelSelect):
    def __init__(self, panel: "SetupPanel"):
        super().__init__(
            placeholder="Canales recomendados (opcional, hasta 5)",
            channel_types=[discord.ChannelType.text],
            min_values=0,
            max_values=5,
        )
        self.panel = panel

    async def callback(self, interaction: discord.Interaction):
        ids = [c.id for c in self.values]
        self.panel.cfg["recommended_channels"] = ids
        await update_config(interaction.guild.id, {"recommended_channels": ids})
        await interaction.response.edit_message(embed=self.panel.build_panel_embed(), view=self.panel)


# ---------- Panel principal ----------

class SetupPanel(discord.ui.View):
    def __init__(self, cfg: dict):
        super().__init__(timeout=300)
        self.cfg = cfg
        self.add_item(ChannelSelect(self))
        self.add_item(RecommendedChannelsSelect(self))

    def build_panel_embed(self):
        cfg = self.cfg
        channel_txt = f"<#{cfg['channel_id']}>" if cfg.get("channel_id") else "No configurado"
        image_txt = cfg.get("image") or "No configurada"
        links_txt = ", ".join(l["label"] for l in cfg.get("links", [])) or "Ninguno"
        rec_txt = ", ".join(f"<#{c}>" for c in cfg.get("recommended_channels", [])) or "Ninguno"

        embed = discord.Embed(
            title="⚙️ Configuración de bienvenida",
            description="Usá los botones y menús para configurar el sistema.",
            color=cfg.get("color", 0x2F3136),
        )
        embed.add_field(name=f"{EMOJI_CHANNEL} Canal", value=channel_txt, inline=True)
        embed.add_field(name=f"{EMOJI_COLOR} Color", value=f"#{cfg['color']:06X}", inline=True)
        embed.add_field(name=f"{EMOJI_IMAGE} Imagen/Gif", value=image_txt, inline=False)
        embed.add_field(name=f"{EMOJI_MESSAGE} Mensaje", value=cfg["message"], inline=False)
        embed.add_field(name=f"{EMOJI_RECOMMENDED} Recomendados", value=rec_txt, inline=False)
        embed.add_field(name=f"{EMOJI_LINKS} Links", value=links_txt, inline=False)
        return embed

    @discord.ui.button(label="Mensaje", emoji=EMOJI_MESSAGE, style=discord.ButtonStyle.secondary, row=2)
    async def set_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MessageModal(self))

    @discord.ui.button(label="Color", emoji=EMOJI_COLOR, style=discord.ButtonStyle.secondary, row=2)
    async def set_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ColorModal(self))

    @discord.ui.button(label="Imagen/Gif", emoji=EMOJI_IMAGE, style=discord.ButtonStyle.secondary, row=2)
    async def set_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ImageModal(self))

    @discord.ui.button(label="Agregar link", emoji=EMOJI_LINKS, style=discord.ButtonStyle.secondary, row=3)
    async def add_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LinkModal(self))

    @discord.ui.button(label="Vista previa", emoji=EMOJI_PREVIEW, style=discord.ButtonStyle.primary, row=3)
    async def preview(self, interaction: discord.Interaction, button: discord.ui.Button):
        fake_embed = build_welcome_embed(self.cfg, interaction.user)
        view = build_links_view(self.cfg)
        await interaction.response.send_message(embed=fake_embed, view=view, ephemeral=True)

    @discord.ui.button(label="Guardar y cerrar", emoji=EMOJI_SAVE, style=discord.ButtonStyle.success, row=3)
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="✅ Configuración guardada.", embed=self.build_panel_embed(), view=None)


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="welcome-setup", description="Configura el sistema de bienvenida del servidor")
    @app_commands.checks.has_permissions(administrator=True)
    async def welcome_setup(self, interaction: discord.Interaction):
        cfg = await get_config(interaction.guild.id)
        panel = SetupPanel(cfg)
        await interaction.response.send_message(embed=panel.build_panel_embed(), view=panel, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = await get_config(member.guild.id)
        if not cfg.get("channel_id"):
            return
        channel = member.guild.get_channel(cfg["channel_id"])
        if not channel:
            return
        embed = build_welcome_embed(cfg, member)
        view = build_links_view(cfg)
        await channel.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
