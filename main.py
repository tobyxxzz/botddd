import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import json
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Dicionários para armazenar dados
tickets = {}
painel_config = {}
ticket_counter = 0
pagamentos_pendentes = {}

CONFIG_FILE = "painel_config.json"

def load_config():
    """Carrega configurações de painéis salvas"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    """Salva configurações de painéis"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot conectado como {bot.user}")
        print(f"📊 Em {len(bot.guilds)} servidor(es)")
        print(f"🔄 {len(synced)} comandos sincronizados!")
    except Exception as e:
        print(f"Erro ao sincronizar: {e}")
    
    global painel_config
    painel_config = load_config()
    
    # Registrar views persistentes
    bot.add_view(TicketCategoryView())
    bot.add_view(PedirUperView())
    bot.add_view(TicketFecharView())
    bot.add_view(PixTicketView(0, "", 0))
    bot.add_view(AprovacaoPixView(0, "", 0, 0))

class TicketModal(discord.ui.Modal, title="Criar Ticket"):
    motivo = discord.ui.TextInput(
        label="Motivo do Ticket",
        placeholder="Ex: Suporte técnico, Reclamação, Dúvida...",
        max_length=100
    )
    
    descricao = discord.ui.TextInput(
        label="Descrição",
        placeholder="Descreva seu problema ou solicitação...",
        style=discord.TextStyle.long,
        max_length=1000
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        global ticket_counter
        
        guild = interaction.guild
        user = interaction.user
        motivo = self.motivo.value
        descricao = self.descricao.value
        
        # Verificar se já existe ticket aberto
        user_tickets = [t for t in tickets.values() if t.get('user_id') == user.id and t.get('status') == 'aberto']
        if user_tickets:
            await interaction.response.send_message("❌ Você já tem um ticket aberto!", ephemeral=True)
            return
        
        ticket_counter += 1
        ticket_name = f"ticket-{ticket_counter}"
        
        try:
            # Criar canal de ticket
            channel = await guild.create_text_channel(
                ticket_name,
                topic=f"Ticket do usuário {user.mention} - {motivo}"
            )
            
            # Armazenar informações do ticket
            tickets[channel.id] = {
                'user_id': user.id,
                'user_name': user.name,
                'motivo': motivo,
                'descricao': descricao,
                'status': 'aberto',
                'criado_em': str(datetime.now())
            }
            
            # Enviar embed no canal do ticket
            embed = discord.Embed(
                title=f"🎫 {motivo}",
                description=descricao,
                color=discord.Color.purple()
            )
            embed.add_field(name="Usuário", value=user.mention, inline=True)
            embed.add_field(name="Status", value="🟢 Aberto", inline=True)
            embed.set_footer(text=f"Ticket ID: {channel.id}")
            
            view = TicketFecharView()
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Ticket criado em {channel.mention}!", ephemeral=True)
            
        except Exception as e:
            print(f"Erro ao criar ticket: {e}")
            await interaction.response.send_message("❌ Erro ao criar ticket!", ephemeral=True)

class TicketCategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.persistent = True
    
    @discord.ui.button(label="Dúvida", style=discord.ButtonStyle.blurple, emoji="❓")
    async def duvida(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await abrir_ticket_categoria(interaction, "Dúvida", "❓")
        except Exception as e:
            print(f"Erro ao criar ticket: {e}")
    
    @discord.ui.button(label="Atendimento", style=discord.ButtonStyle.primary, emoji="👤")
    async def atendimento(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await abrir_ticket_categoria(interaction, "Atendimento", "👤")
        except Exception as e:
            print(f"Erro ao criar ticket: {e}")
    
    @discord.ui.button(label="Suporte", style=discord.ButtonStyle.success, emoji="🛠️")
    async def suporte(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await abrir_ticket_categoria(interaction, "Suporte", "🛠️")
        except Exception as e:
            print(f"Erro ao criar ticket: {e}")
    
    @discord.ui.button(label="Reclamação", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def reclamacao(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await abrir_ticket_categoria(interaction, "Reclamação", "⚠️")
        except Exception as e:
            print(f"Erro ao criar ticket: {e}")

class PedirUperView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.persistent = True
    
    @discord.ui.button(label="TICKET UPER", style=discord.ButtonStyle.primary, emoji="👑")
    async def pedir_uper(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await abrir_ticket_categoria(interaction, "Pedir Uper", "👑")
        except Exception as e:
            print(f"Erro ao criar ticket: {e}")

async def abrir_ticket_categoria(interaction: discord.Interaction, categoria: str, emoji: str):
    """Função auxiliar para abrir tickets com categoria"""
    global ticket_counter
    
    user = interaction.user
    guild = interaction.guild
    
    try:
        # Verificar se já existe ticket aberto
        user_tickets = [t for t in tickets.values() if t.get('user_id') == user.id and t.get('status') == 'aberto']
        if user_tickets:
            await interaction.response.send_message("❌ Você já tem um ticket aberto!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        ticket_counter += 1
        ticket_name = f"ticket-{ticket_counter}"
        
        # Criar canal de ticket
        channel = await guild.create_text_channel(
            ticket_name,
            topic=f"{categoria} - {user.mention}"
        )
        
        # Armazenar informações do ticket
        tickets[channel.id] = {
            'user_id': user.id,
            'user_name': user.name,
            'motivo': categoria,
            'descricao': '',
            'status': 'aberto',
            'criado_em': str(datetime.now())
        }
        
        # Configurar permissões do canal
        try:
            # Bloquear @everyone
            await channel.set_permissions(guild.default_role, view_channel=False, send_messages=False)
            
            # Permitir o usuário
            await channel.set_permissions(user, view_channel=True, send_messages=True)
            
            # Permitir equipe
            config = painel_config.get(str(guild.id), {})
            equipe = config.get('equipe', [])
            for user_id in equipe:
                member = guild.get_member(user_id)
                if member:
                    await channel.set_permissions(member, view_channel=True, send_messages=True)
        except Exception as e:
            print(f"Erro ao configurar permissões: {e}")
        
        # Enviar embed no canal do ticket
        embed = discord.Embed(
            title=f"{emoji} {categoria}",
            description=f"Bem-vindo ao seu ticket de {categoria.lower()}!",
            color=discord.Color.purple()
        )
        embed.add_field(name="Usuário", value=user.mention, inline=True)
        embed.add_field(name="Status", value="🟢 Aberto", inline=True)
        embed.add_field(name="📝", value="Descreva seu problema ou dúvida abaixo!", inline=False)
        embed.set_footer(text=f"Ticket ID: {channel.id}")
        
        view = TicketFecharView()
        await channel.send(embed=embed, view=view)
        await interaction.followup.send(f"✅ Ticket criado em {channel.mention}!", ephemeral=True)
        
    except Exception as e:
        print(f"Erro ao criar ticket: {e}")
        try:
            await interaction.followup.send(f"❌ Erro ao criar ticket: {str(e)}", ephemeral=True)
        except:
            pass

class TicketFecharView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger, emoji="🔒")
    async def fechar_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        
        if channel.id not in tickets:
            await interaction.response.send_message("❌ Ticket não encontrado!", ephemeral=True)
            return
        
        ticket = tickets[channel.id]
        ticket['status'] = 'fechado'
        
        embed = discord.Embed(
            title="🔒 Ticket Fechado",
            description="Este ticket foi arquivado.",
            color=discord.Color.red()
        )
        
        await interaction.response.defer()
        await channel.send(embed=embed)
        await channel.edit(archived=True)

class ComprarButton(discord.ui.Button):
    def __init__(self, cargo_name, meses, valor, guild_id):
        super().__init__(label="🛒 Comprar", style=discord.ButtonStyle.green, emoji="💳")
        self.cargo_name = cargo_name
        self.meses = meses
        self.valor = valor
        self.guild_id = guild_id
    
    async def callback(self, interaction: discord.Interaction):
        global ticket_counter, painel_config
        
        user = interaction.user
        guild = interaction.guild
        
        try:
            # Verificar se já existe ticket aberto
            user_tickets = [t for t in tickets.values() if t.get('user_id') == user.id and t.get('status') == 'aberto']
            if user_tickets:
                await interaction.response.send_message("❌ Você já tem um ticket aberto!", ephemeral=True)
                return
            
            ticket_counter += 1
            ticket_name = f"pix-{ticket_counter}"
            
            # Criar canal de ticket para PIX
            channel = await guild.create_text_channel(
                ticket_name,
                topic=f"Compra de {self.cargo_name} - {user.name}"
            )
            
            # Armazenar informações do ticket
            tickets[channel.id] = {
                'user_id': user.id,
                'user_name': user.name,
                'motivo': f"Compra - {self.cargo_name}",
                'status': 'aberto',
                'criado_em': str(datetime.now()),
                'cargo_name': self.cargo_name,
                'meses': self.meses,
                'valor': self.valor
            }
            
            # Configurar permissões do canal
            try:
                # Bloquear @everyone
                await channel.set_permissions(guild.default_role, view_channel=False, send_messages=False)
                
                # Permitir o usuário
                await channel.set_permissions(user, view_channel=True, send_messages=True)
                
                # Permitir equipe
                config = painel_config.get(str(guild.id), {})
                equipe = config.get('equipe', [])
                for user_id in equipe:
                    member = guild.get_member(user_id)
                    if member:
                        await channel.set_permissions(member, view_channel=True, send_messages=True)
            except Exception as e:
                print(f"Erro ao configurar permissões PIX: {e}")
            
            # Buscar PIX key do config
            config = painel_config.get(str(guild.id), {})
            pix_key = config.get('pix_key', '❌ PIX não configurado')
            
            # Enviar embed com PIX
            embed = discord.Embed(
                title=f"💳 Pagamento via PIX",
                description=f"**Cargo:** {self.cargo_name}\n**Duração:** {self.meses} mês(es)",
                color=discord.Color.purple()
            )
            
            if self.valor:
                embed.add_field(name="Valor", value=f"R$ {self.valor}", inline=False)
            
            embed.add_field(name="📲 Chave PIX", value=f"`{pix_key}`", inline=False)
            
            try:
                embed.set_image(url="attachment://venom_store.gif")
                file = discord.File("venom_store.gif", filename="venom_store.gif")
                view = PixTicketView(user.id, self.cargo_name, self.meses)
                await channel.send(embed=embed, file=file, view=view)
            except:
                # Se falhar ao enviar com GIF, envia sem
                view = PixTicketView(user.id, self.cargo_name, self.meses)
                await channel.send(embed=embed, view=view)
            
            await interaction.response.send_message(f"✅ Ticket de compra criado em {channel.mention}!", ephemeral=True)
            
        except Exception as e:
            print(f"Erro ao criar ticket de PIX: {e}")
            try:
                await interaction.response.send_message(f"❌ Erro ao criar ticket: {str(e)}", ephemeral=True)
            except:
                pass

class PixTicketView(discord.ui.View):
    def __init__(self, user_id, cargo_name, meses):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.cargo_name = cargo_name
        self.meses = meses
        self.persistent = True
    
    @discord.ui.button(label="Copiar PIX", style=discord.ButtonStyle.gray, emoji="📋")
    async def copiar(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            config = painel_config.get(str(interaction.guild.id), {})
            pix_key = config.get('pix_key', 'Não configurado')
            await interaction.response.send_message(f"✅ Chave PIX copiada: `{pix_key}`", ephemeral=True)
        except Exception as e:
            print(f"Erro ao copiar PIX: {e}")
    
    @discord.ui.button(label="Já Comprei", style=discord.ButtonStyle.success, emoji="✅")
    async def ja_comprei(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild = interaction.guild
            config = painel_config.get(str(guild.id), {})
            owner_id = config.get('owner_id')
            
            # Enviar DM ao dono
            if owner_id:
                try:
                    owner = await interaction.client.fetch_user(int(owner_id))
                    embed = discord.Embed(
                        title="👑 Novo Pagamento Pendente",
                        description=f"{interaction.user.mention} diz que já pagou!",
                        color=discord.Color.gold()
                    )
                    embed.add_field(name="Usuário", value=f"{interaction.user.mention} ({interaction.user.name})", inline=False)
                    embed.add_field(name="Cargo", value=self.cargo_name, inline=True)
                    embed.add_field(name="Duração", value=f"{self.meses} mês(es)", inline=True)
                    embed.add_field(name="📍 Ticket", value=interaction.channel.mention, inline=False)
                    
                    view = AprovacaoPixView(self.user_id, self.cargo_name, self.meses, guild.id)
                    await owner.send(embed=embed, view=view)
                except Exception as e:
                    print(f"Erro ao enviar DM ao dono: {e}")
            
            # Avisar o cliente
            await interaction.response.send_message(
                "⏳ Você será analisado em breve!\n\n"
                "👑 O dono do servidor foi notificado e em breve um admin verificará seu pagamento.\n"
                "Aguarde a confirmação aqui no ticket!",
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro ao processar 'Já Comprei': {e}")

class AprovacaoPixView(discord.ui.View):
    def __init__(self, user_id, cargo_name, meses, guild_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.cargo_name = cargo_name
        self.meses = meses
        self.guild_id = guild_id
        self.persistent = True
    
    @discord.ui.button(label="Aprovar", style=discord.ButtonStyle.success, emoji="✅")
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild = interaction.client.get_guild(self.guild_id)
            
            try:
                member = await interaction.client.fetch_user(self.user_id)
                guild_member = guild.get_member(self.user_id)
            except:
                member = None
                guild_member = None
            
            cargo_name = self.cargo_name
            if not cargo_name or cargo_name.strip() == "":
                cargo_name = "Membro VIP"
            
            cargo = discord.utils.get(guild.roles, name=cargo_name)
            
            if not cargo:
                try:
                    cargo = await guild.create_role(name=cargo_name, color=discord.Color.gold())
                except Exception as e:
                    print(f"Erro ao criar cargo: {e}")
                    await interaction.response.send_message(f"❌ Erro ao criar cargo '{cargo_name}'!", ephemeral=True)
                    return
            
            if guild_member:
                try:
                    await guild_member.add_roles(cargo)
                except Exception as e:
                    print(f"Erro ao adicionar cargo: {e}")
                    await interaction.response.send_message(f"❌ Erro ao adicionar cargo ao membro!", ephemeral=True)
                    return
            
            # Calcular data de expiração
            expiry_date = (datetime.now() + timedelta(days=self.meses * 30)).strftime("%d/%m/%Y")
            
            embed = discord.Embed(
                title="✅ Pagamento Aprovado!",
                description=f"Você aprovou o pagamento de <@{self.user_id}>!",
                color=discord.Color.green()
            )
            embed.add_field(name="Cargo", value=cargo_name, inline=True)
            embed.add_field(name="Duração", value=f"{self.meses} mês(es)", inline=True)
            embed.add_field(name="Data de Expiração", value=f"**{expiry_date}**", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            if member:
                try:
                    await member.send(f"✅ Seu pagamento foi aprovado! Você tem o cargo **{cargo_name}** até **{expiry_date}**!")
                except:
                    pass
        except Exception as e:
            print(f"Erro ao aprovar pagamento: {e}")
            try:
                await interaction.response.send_message(f"❌ Erro ao aprovar: {str(e)}", ephemeral=True)
            except:
                pass
    
    @discord.ui.button(label="Rejeitar", style=discord.ButtonStyle.danger, emoji="❌")
    async def rejeitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            try:
                member = await interaction.client.fetch_user(self.user_id)
            except:
                member = None
            
            embed = discord.Embed(
                title="❌ Pagamento Rejeitado",
                description=f"Você rejeitou o pagamento de <@{self.user_id}>.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            if member:
                try:
                    await member.send(f"❌ Seu pagamento foi rejeitado pelo dono do servidor.")
                except:
                    pass
        except Exception as e:
            print(f"Erro ao rejeitar pagamento: {e}")

@bot.tree.command(name="pedir_uper", description="Painel para pedir uper")
async def pedir_uper(interaction: discord.Interaction):
    """Mostra o painel para pedir uper"""
    embed = discord.Embed(
        title="UPER",
        description="Confirme os valores de serviço em <#1443037178358665306>\nVou solicitar um UPER, você concorda com nossos termos e condições em <#1443036865937674250>\nVocê receberá entregas em <#1443037457351180430>\nAs regiões de serviços estão em <#1443037600763088937>",
        color=discord.Color.from_rgb(88, 101, 242)
    )
    
    view = PedirUperView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="painel", description="Painel de tickets")
async def painel(interaction: discord.Interaction):
    """Mostra o painel de criação de tickets"""
    embed = discord.Embed(
        title="🎫 Painel de Tickets",
        description="Escolha o tipo de ticket que você precisa:",
        color=discord.Color.purple()
    )
    embed.add_field(name="❓ Dúvida", value="Tenha uma dúvida? Abra um ticket!", inline=False)
    embed.add_field(name="👤 Atendimento", value="Precisa de atendimento? Clique aqui!", inline=False)
    embed.add_field(name="🛠️ Suporte", value="Problemas técnicos? Estamos aqui!", inline=False)
    embed.add_field(name="⚠️ Reclamação", value="Alguma reclamação? Nos avise!", inline=False)
    
    view = TicketCategoryView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="criar_ticket", description="Cria um novo ticket")
async def criar_ticket(interaction: discord.Interaction):
    """Abre um modal para o usuário criar um ticket"""
    await interaction.response.send_modal(TicketModal())

@bot.tree.command(name="fechar_ticket", description="Fecha um ticket")
async def fechar_ticket(interaction: discord.Interaction):
    """Fecha o ticket do canal atual"""
    if interaction.channel.id not in tickets:
        await interaction.response.send_message("❌ Este não é um canal de ticket!")
        return
    
    ticket = tickets[interaction.channel.id]
    ticket['status'] = 'fechado'
    
    embed = discord.Embed(
        title="🔒 Ticket Fechado",
        description="Este ticket foi arquivado.",
        color=discord.Color.red()
    )
    
    await interaction.response.defer()
    await interaction.channel.send(embed=embed)
    await interaction.channel.edit(archived=True)

@bot.tree.command(name="reabrir", description="Reabre um ticket")
async def reabrir(interaction: discord.Interaction):
    """Reabre um ticket"""
    if interaction.channel.id not in tickets:
        await interaction.response.send_message("❌ Este não é um canal de ticket!")
        return
    
    ticket = tickets[interaction.channel.id]
    ticket['status'] = 'aberto'
    
    embed = discord.Embed(
        title="🔓 Ticket Reaberto",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)
    await interaction.channel.edit(archived=False)

@bot.tree.command(name="configurar_pix", description="Configura a chave PIX do servidor")
async def configurar_pix(interaction: discord.Interaction, chave_pix: str):
    """Configura a chave PIX para o servidor"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Apenas administradores!")
        return
    
    global painel_config
    guild_id = str(interaction.guild.id)
    
    if guild_id not in painel_config:
        painel_config[guild_id] = {}
    
    painel_config[guild_id]['pix_key'] = chave_pix
    save_config(painel_config)
    
    embed = discord.Embed(
        title="✅ PIX Configurado",
        description=f"Chave PIX: `{chave_pix}`",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="pix", description="Cria painel de compra via PIX")
async def pix(interaction: discord.Interaction, cargo: str, meses: int = 1, valor: str = ""):
    """Envia painel de compra com botão Comprar"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Apenas administradores!")
        return
    
    desc = f"**Cargo:** {cargo}\n**Duração:** {meses} mês(es)"
    if valor:
        desc += f"\n**Valor:** R$ {valor}"
    desc += "\n\nClique no botão abaixo para comprar!"
    
    embed = discord.Embed(
        title="💳 Loja de Cargos",
        description=desc,
        color=discord.Color.purple()
    )
    
    embed.set_image(url="attachment://venom_store.gif")
    file = discord.File("venom_store.gif", filename="venom_store.gif")
    view = discord.ui.View()
    view.add_item(ComprarButton(cargo, meses, valor, interaction.guild.id))
    
    await interaction.response.send_message(embed=embed, file=file, view=view)

@bot.tree.command(name="stats", description="Mostra estatísticas de tickets")
async def stats(interaction: discord.Interaction):
    """Mostra estatísticas"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Apenas administradores!")
        return
    
    total = len(tickets)
    abertos = sum(1 for t in tickets.values() if t.get('status') == 'aberto')
    fechados = total - abertos
    
    embed = discord.Embed(
        title="📊 Estatísticas de Tickets",
        color=discord.Color.blurple()
    )
    embed.add_field(name="📌 Total", value=str(total), inline=True)
    embed.add_field(name="🟢 Abertos", value=str(abertos), inline=True)
    embed.add_field(name="🔴 Fechados", value=str(fechados), inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="mensagem", description="Enviar uma mensagem de texto customizada")
async def mensagem(
    interaction: discord.Interaction, 
    titulo: str, 
    texto: str,
    embed_option: bool = True
):
    """Envia uma mensagem com título e texto, opcionalmente com embed e GIF"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Apenas administradores podem usar este comando!")
        return
    
    if embed_option:
        embed = discord.Embed(
            title=titulo,
            description=texto,
            color=discord.Color.purple()
        )
        embed.set_image(url="attachment://venom_store.gif")
        file = discord.File("venom_store.gif", filename="venom_store.gif")
        await interaction.channel.send(embed=embed, file=file)
    else:
        await interaction.channel.send(f"**{titulo}**\n{texto}")
    
    await interaction.response.send_message("✅ Mensagem enviada!", ephemeral=True)

@bot.tree.command(name="registrar_dono", description="Registra o ID do dono do servidor")
async def registrar_dono(interaction: discord.Interaction, dono_id: str):
    """Registra o ID do dono para receber notificações"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Apenas administradores!")
        return
    
    global painel_config
    
    try:
        dono_id_int = int(dono_id)
        guild_id = str(interaction.guild.id)
        
        if guild_id not in painel_config:
            painel_config[guild_id] = {}
        
        painel_config[guild_id]['owner_id'] = dono_id_int
        save_config(painel_config)
        
        embed = discord.Embed(
            title="✅ Dono Registrado",
            description=f"ID do dono: `{dono_id_int}`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except ValueError:
        await interaction.response.send_message("❌ ID inválido! Use apenas números.", ephemeral=True)

@bot.tree.command(name="adicionar_equipe", description="Adiciona um membro à equipe de suporte")
async def adicionar_equipe(interaction: discord.Interaction, usuario: discord.User):
    """Adiciona um usuário à equipe de suporte"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Apenas administradores!")
        return
    
    global painel_config
    guild_id = str(interaction.guild.id)
    
    if guild_id not in painel_config:
        painel_config[guild_id] = {}
    
    if 'equipe' not in painel_config[guild_id]:
        painel_config[guild_id]['equipe'] = []
    
    if usuario.id not in painel_config[guild_id]['equipe']:
        painel_config[guild_id]['equipe'].append(usuario.id)
        save_config(painel_config)
        
        embed = discord.Embed(
            title="✅ Membro Adicionado",
            description=f"{usuario.mention} foi adicionado à equipe de suporte!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ {usuario.mention} já está na equipe!", ephemeral=True)

@bot.tree.command(name="remover_equipe", description="Remove um membro da equipe de suporte")
async def remover_equipe(interaction: discord.Interaction, usuario: discord.User):
    """Remove um usuário da equipe de suporte"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Apenas administradores!")
        return
    
    global painel_config
    guild_id = str(interaction.guild.id)
    
    if guild_id not in painel_config or 'equipe' not in painel_config[guild_id]:
        await interaction.response.send_message("❌ Nenhuma equipe configurada!", ephemeral=True)
        return
    
    if usuario.id in painel_config[guild_id]['equipe']:
        painel_config[guild_id]['equipe'].remove(usuario.id)
        save_config(painel_config)
        
        embed = discord.Embed(
            title="✅ Membro Removido",
            description=f"{usuario.mention} foi removido da equipe de suporte!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ {usuario.mention} não está na equipe!", ephemeral=True)

@bot.tree.command(name="listar_equipe", description="Lista os membros da equipe de suporte")
async def listar_equipe(interaction: discord.Interaction):
    """Lista todos os membros da equipe de suporte"""
    global painel_config
    guild_id = str(interaction.guild.id)
    
    if guild_id not in painel_config or 'equipe' not in painel_config[guild_id] or not painel_config[guild_id]['equipe']:
        await interaction.response.send_message("❌ Nenhuma equipe configurada!", ephemeral=True)
        return
    
    equipe_list = painel_config[guild_id]['equipe']
    guild = interaction.guild
    
    membros = []
    for user_id in equipe_list:
        try:
            user = await interaction.client.fetch_user(user_id)
            membros.append(f"• {user.mention} ({user.name})")
        except:
            membros.append(f"• ID: {user_id} (Usuário não encontrado)")
    
    embed = discord.Embed(
        title="👥 Equipe de Suporte",
        description="\n".join(membros) if membros else "Nenhum membro",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Total: {len(membros)} membros")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Token do bot
TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN)
