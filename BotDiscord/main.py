import discord
from discord.ext import commands, tasks
import aiohttp
from bs4 import BeautifulSoup
import asyncio
import os
import datetime
import json
from dotenv import load_dotenv

load_dotenv()

ARQUIVO_MONITORAMENTO = "monitoramento.json"

intents = discord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

monitoramento_por_canal = {}

def salvar_monitoramento():
    try:
        with open(ARQUIVO_MONITORAMENTO, "w", encoding="utf-8") as f:
            json.dump(monitoramento_por_canal, f, ensure_ascii=False, indent=4)
        print("📁 Arquivo de monitoramento salvo com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao salvar monitoramento: {e}")

def carregar_monitoramento():
    global monitoramento_por_canal
    if os.path.exists(ARQUIVO_MONITORAMENTO):
        try:
            with open(ARQUIVO_MONITORAMENTO, "r", encoding="utf-8") as f:
                monitoramento_por_canal = json.load(f)
                monitoramento_por_canal = {int(k): v for k, v in monitoramento_por_canal.items()}
            print(f"📂 Monitoramento carregado: {monitoramento_por_canal}")
        except Exception as e:
            print(f"❌ Erro ao carregar monitoramento: {e}")
    else:
        print("📂 Arquivo de monitoramento não encontrado, iniciando com dicionário vazio.")

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    carregar_monitoramento()
    if not almosso.is_running():
        almosso.start()
    if monitoramento_por_canal and not monitorar_links.is_running():
        monitorar_links.start()


@bot.command(name="monitorar")
async def iniciar_monitoramento(ctx):
    await ctx.send("📥 Envie o link da **página** que eu devo monitorar:")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", check=check, timeout=60)
        pagina_url = msg.content.strip()
        canal_id = ctx.channel.id

        if canal_id not in monitoramento_por_canal:
            monitoramento_por_canal[canal_id] = {}

        if pagina_url in monitoramento_por_canal[canal_id]:
            await ctx.send("⚠️ Esse link já está sendo monitorado neste canal.")
            return

        link_inicial = await extrair_primeiro_link(pagina_url)

        monitoramento_por_canal[canal_id][pagina_url] = link_inicial or None
        salvar_monitoramento()

        if link_inicial:
            await ctx.send(f"✅ Link `{pagina_url}` adicionado com sucesso. Primeiro link encontrado: {link_inicial}")
        else:
            await ctx.send("⚠️ Link adicionado, mas não foi possível extrair um link da página.")

        if not monitorar_links.is_running():
            monitorar_links.start()

    except asyncio.TimeoutError:
        await ctx.send("⏰ Tempo esgotado. Por favor, tente novamente usando `!monitorar`.")

async def extrair_primeiro_link(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    a_tag = soup.find('a')
                    if a_tag and a_tag.has_attr('href'):
                        return a_tag['href']
    except Exception as e:
        print(f"Erro ao extrair link da página: {e}")
    return None

@tasks.loop(seconds=60)
async def monitorar_links():
    for canal_id, urls in monitoramento_por_canal.items():
        canal = bot.get_channel(canal_id)
        if not canal:
            continue

        for url, ultimo_link in list(urls.items()):
            link_atual = await extrair_primeiro_link(url)
            if link_atual and link_atual != ultimo_link:
                monitoramento_por_canal[canal_id][url] = link_atual
                salvar_monitoramento()
                await canal.send(f"🔗 Novo link encontrado em `{url}`: {link_atual}")

@bot.command()
async def limpar(ctx):
    canal = ctx.channel
    novo_canal = await canal.clone(reason="Limpar todas as mensagens")
    await canal.delete()
    await novo_canal.send("✅ Canal limpo com sucesso!", delete_after=5)

@bot.command(name="listar")
async def listar_links(ctx):
    canal_id = ctx.channel.id
    links = monitoramento_por_canal.get(canal_id)

    if not links:
        await ctx.send("📭 Nenhum link está sendo monitorado neste canal.")
        return

    mensagem = "**🔗 Links monitorados neste canal:**\n"
    for i, url in enumerate(links.keys(), start=1):
        mensagem += f"{i}. `{url}`\n"

    await ctx.send(mensagem)

@bot.command(name="buscar_links")
async def buscar_links(ctx):
    await ctx.send("🔍 Envie o link base para buscar todos os links presentes nessa página:")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", check=check, timeout=60)
        link_base = msg.content.strip()

        async with aiohttp.ClientSession() as session:
            async with session.get(link_base) as resp:
                if resp.status != 200:
                    await ctx.send(f"❌ Não foi possível acessar a página. Status: {resp.status}")
                    return
                html = await resp.text()

        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.startswith('http'):
                links.add(href)

        if not links:
            await ctx.send("❌ Nenhum link encontrado na página.")
            return

        resposta = "**🔗 Links encontrados na página:**\n"
        for i, url in enumerate(links, 1):
            resposta += f"{i}. {url}\n"
            if i >= 10:
                resposta += f"...e mais {len(links) - 10} links encontrados."
                break

        await ctx.send(resposta)

    except asyncio.TimeoutError:
        await ctx.send("⏰ Tempo esgotado. Por favor, tente novamente.")
    except Exception as e:
        await ctx.send(f"⚠️ Ocorreu um erro: {e}")


@bot.command(name="remover")
async def remover_link(ctx):
    canal_id = ctx.channel.id
    links = monitoramento_por_canal.get(canal_id)

    if not links:
        await ctx.send("📭 Nenhum link está sendo monitorado neste canal.")
        return

    lista_links = list(links.keys())
    mensagem = "**❌ Qual link você quer remover?**\n"
    for i, url in enumerate(lista_links, start=1):
        mensagem += f"{i}. `{url}`\n"
    mensagem += "\nDigite o **número** correspondente ao link para removê-lo."

    await ctx.send(mensagem)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", check=check, timeout=60)
        escolha = int(msg.content)

        if 1 <= escolha <= len(lista_links):
            url_removida = lista_links[escolha - 1]
            del monitoramento_por_canal[canal_id][url_removida]
            salvar_monitoramento()
            await ctx.send(f"✅ Link removido: `{url_removida}`")

            if not monitoramento_por_canal[canal_id]:
                del monitoramento_por_canal[canal_id]
                salvar_monitoramento()

        else:
            await ctx.send("❌ Número inválido.")

    except asyncio.TimeoutError:
        await ctx.send("⏰ Tempo esgotado. Por favor, tente novamente.")
    except ValueError:
        await ctx.send("⚠️ Entrada inválida. Digite apenas o número do link.")

@bot.event
async def on_member_join(member: discord.Member):
    canal = bot.get_channel(1374768524295405700)
    if canal:
        await canal.send(f'👉 {member.mention} entrou no servidor!')

@bot.event
async def on_member_remove(member: discord.Member):
    canal = bot.get_channel(1375143277128454184)
    if canal:
        await canal.send(f'Até mais {member.mention} 😃!')

@tasks.loop(minutes=30)
async def almosso():
    agora = datetime.datetime.now()
    if agora.hour == 12 and agora.minute == 30:
        canal = bot.get_channel(1374444227370422384)
        if canal:
            minha_embed = discord.Embed(
                title="O dono desse servidor almossou",
                description="O dono não tankou o al-mosso"
            )

            if os.path.exists("imagem_gato.jpg"):
                imagem = discord.File("imagem_gato.jpg", "gato.jpg")
                minha_embed.set_image(url="attachment://gato.jpg")
                await canal.send(embed=minha_embed, file=imagem)
            else:
                await canal.send("⚠️ Imagem 'imagem_gato.jpg' não encontrada.")


@bot.command(name="buscar_historico")
async def buscar_historico(ctx):
    await ctx.send("🔍 Envie o link base para buscar todos os links históricos dessa página:")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", check=check, timeout=60)
        link_base = msg.content.strip()

        # Obter as capturas da página base
        cdx_url = "http://web.archive.org/cdx/search/cdx"
        params = {
            "url": link_base,
            "output": "json",
            "fl": "timestamp,original",
            "collapse": "digest"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(cdx_url, params=params) as resp:
                if resp.status != 200:
                    await ctx.send(f"❌ Não foi possível acessar a API da Wayback Machine. Status: {resp.status}")
                    return
                data = await resp.json()

        if len(data) <= 1:
            await ctx.send("❌ Nenhuma versão arquivada encontrada para essa URL.")
            return

        # Extrair os links de cada versão arquivada
        links_encontrados = set()
        for entry in data[1:]:
            timestamp = entry[0]
            archived_url = f"http://web.archive.org/web/{timestamp}/{link_base}"

            async with aiohttp.ClientSession() as session:
                async with session.get(archived_url) as resp:
                    if resp.status != 200:
                        continue
                    html = await resp.text()

            soup = BeautifulSoup(html, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if href.startswith('http'):
                    links_encontrados.add(href)

        if not links_encontrados:
            await ctx.send("❌ Nenhum link encontrado nas versões arquivadas da página.")
            return

        resposta = "**🔗 Links encontrados nas versões arquivadas:**\n"
        for i, url in enumerate(links_encontrados, 1):
            resposta += f"{i}. {url}\n"
            if i >= 10:
                resposta += f"...e mais {len(links_encontrados) - 10} links encontrados."
                break

        await ctx.send(resposta)

    except asyncio.TimeoutError:
        await ctx.send("⏰ Tempo esgotado. Por favor, tente novamente.")
    except Exception as e:
        await ctx.send(f"⚠️ Ocorreu um erro: {e}")


bot.run(os.getenv("TOKEN"))
