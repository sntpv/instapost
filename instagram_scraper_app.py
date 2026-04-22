import streamlit as st
import instaloader
import re
import os
import requests
from requests.auth import HTTPBasicAuth
from PIL import Image
from streamlit_cropper import st_cropper
import io

st.set_page_config(page_title="Instagram to WP - sntpvenav", page_icon="📸", layout="wide")

# Inicializando as variáveis da sessão do Streamlit
if 'post_caption' not in st.session_state:
    st.session_state.post_caption = None
if 'images' not in st.session_state:
    st.session_state.images = []
if 'shortcode' not in st.session_state:
    st.session_state.shortcode = None
if 'cropped_img' not in st.session_state:
    st.session_state.cropped_img = None
if 'wp_categories' not in st.session_state:
    st.session_state.wp_categories = []
if 'wp_tags' not in st.session_state:
    st.session_state.wp_tags = []

def get_wp_data(url, user, password, endpoint):
    """Busca dados da API do WordPress."""
    try:
        response = requests.get(
            f"{url.rstrip('/')}/wp-json/wp/v2/{endpoint}?per_page=100",
            auth=HTTPBasicAuth(user, password),
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        return []

def convert_urls_to_html(text):
    """Converte URLs em links HTML clicáveis."""
    def replace(match):
        url = match.group(0)
        href = url if url.startswith('http') else 'http://' + url
        return f'<a href="{href}" target="_blank">{url}</a>'
    url_pattern = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'
    return re.sub(url_pattern, replace, text)

st.title("Coletor de Posts e Publicador WordPress")
st.markdown("Busque posts **exclusivamente do perfil sntpvenav** e prepare as imagens e o texto para publicar diretamente via API no seu site WordPress.")

url = st.text_input("Insira a URL do post do Instagram:")

def extract_shortcode(url):
    """Extrai o ID do post (shortcode) da URL."""
    match = re.search(r'/(?:p|reel)/([^/?]+)', url)
    if match:
        return match.group(1)
    return None

if st.button("Buscar e Baixar Dados"):
    if url:
        shortcode = extract_shortcode(url)
        if shortcode:
            with st.spinner("Conectando ao Instagram e buscando informações..."):
                L = instaloader.Instaloader(
                    download_videos=False,
                    save_metadata=False,
                    post_metadata_txt_pattern='{caption}'
                )
                try:
                    post = instaloader.Post.from_shortcode(L.context, shortcode)
                    if post.owner_username != 'sntpvenav':
                        st.error(f"Acesso Negado! O post inserido pertence ao perfil '{post.owner_username}'. Este aplicativo permite visualizar apenas conteúdos do perfil 'sntpvenav'.")
                    else:
                        st.success(f"Post validado e baixado! (Perfil: {post.owner_username})")
                        target_dir = f"post_{shortcode}"
                        L.download_post(post, target=target_dir)
                        
                        # Salva na memória do aplicativo o texto e o shortcode
                        st.session_state.post_caption = post.caption if post.caption else ""
                        st.session_state.shortcode = shortcode
                        st.session_state.images = []
                        
                        # Adiciona as imagens baixadas à sessão
                        if os.path.exists(target_dir):
                            for file in sorted(os.listdir(target_dir)):
                                if file.lower().endswith(('.jpg', '.png', '.jpeg')):
                                    st.session_state.images.append(os.path.join(target_dir, file))
                                    
                except Exception as e:
                    st.error(f"Ocorreu um erro ao tentar buscar as informações: {e}")
        else:
            st.warning("Por favor, insira uma URL válida.")
    else:
        st.warning("O campo de URL não pode estar vazio.")

# -- Interface Extraída (Preparação para o WordPress) --
if st.session_state.post_caption is not None:
    st.markdown("---")
    st.subheader("⚙️ Configurações do WordPress")
    
    # Inputs para configuração de publicação de posts
    wp_col1, wp_col2, wp_col3, wp_col4 = st.columns([2, 2, 2, 1])
    with wp_col1:
        wp_url = st.text_input("URL do site WP API (ex: http://localhost:8080)", value="http://localhost:8080")
    with wp_col2:
        wp_user = st.text_input("Usuário do WP")
    with wp_col3:
        wp_pass = st.text_input("Senha de Aplicativo (Application Password)", type="password")
    with wp_col4:
        wp_status = st.selectbox("Status", ["draft", "publish", "private"], index=0)

    # Botão de Sincronização
    if st.button("🔄 Sincronizar Categorias e Tags"):
        if wp_url and wp_user and wp_pass:
            with st.spinner("Buscando dados do WordPress..."):
                st.session_state.wp_categories = get_wp_data(wp_url, wp_user, wp_pass, "categories")
                st.session_state.wp_tags = get_wp_data(wp_url, wp_user, wp_pass, "tags")
                if not st.session_state.wp_categories and not st.session_state.wp_tags:
                    st.warning("Nenhuma categoria ou tag encontrada ou erro na conexão. Verifique as credenciais.")
                else:
                    st.success(f"Sincronizado! ({len(st.session_state.wp_categories)} categorias, {len(st.session_state.wp_tags)} tags)")
        else:
            st.warning("Preencha as credenciais do WordPress primeiro.")

    st.markdown("---")
    st.subheader("📝 Preparar e Publicar Post")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        post_title = st.text_input("Título do Post no WordPress", value=f"Post do Instagram - {st.session_state.shortcode}")
        
        col_tax1, col_tax2 = st.columns(2)
        with col_tax1:
            cat_options = {c['name']: c['id'] for c in st.session_state.wp_categories}
            selected_cats = st.multiselect("Categorias", options=list(cat_options.keys()), 
                                          default=[name for name, id in cat_options.items() if id == 1] if 1 in cat_options.values() else [])
            if not cat_options:
                st.info("Clique em 'Sincronizar' para carregar categorias.")
        with col_tax2:
            tag_options = {t['name']: t['id'] for t in st.session_state.wp_tags}
            selected_tags = st.multiselect("Tags Existentes", options=list(tag_options.keys()), default=[])
            if not tag_options:
                st.info("Clique em 'Sincronizar' para carregar tags.")
            extra_tags_input = st.text_input("Novas Tags (Nomes separados por vírgula)", help="Ex: Promoção, Verão, 2024")
        
        # Converter linhas do texto base para parágrafos HTML simples (para o editor)
        processed_caption = convert_urls_to_html(st.session_state.post_caption)
        paragraphs = [f"<p>{p.strip()}</p>" for p in processed_caption.split('\n') if p.strip()]
        html_formatted_text = "\n".join(paragraphs)
        
        edited_content = st.text_area("Corpo de Texto do Post (Aceita marcação HTML)", value=html_formatted_text, height=450)
    
    with col2:
        st.write("**Definição da Imagem Destacada**")
        mode_destaque = st.radio("Método da Imagem Destacada", 
                                 ["Recortar foto do Instagram", "Informar ID de mídia fixa (WP)"], 
                                 index=0, horizontal=True)
        
        media_id_manual = None
        
        if mode_destaque == "Recortar foto do Instagram":
            if st.session_state.images:
                selected_img_name = st.selectbox("Selecione a Imagem da Lista", st.session_state.images)
                
                # Ferramenta de Recorte
                img = Image.open(selected_img_name)
                
                aspect_choice = st.radio("Proporção do Recorte", ["Livre", "16:9", "4:3", "1:1"], index=1, horizontal=True)
                aspect_dict = {"Livre": None, "16:9": (16, 9), "4:3": (4, 3), "1:1": (1, 1)}
                
                # O st_cropper retorna um objeto PIL Image
                cropped_img = st_cropper(img, realtime_update=True, box_color='#FF0000', 
                                         aspect_ratio=aspect_dict[aspect_choice])
                
                # Preview do recorte
                st.write("Preview do Recorte:")
                st.image(cropped_img, width='stretch')
                st.session_state.cropped_img = cropped_img
            else:
                st.info("Nenhuma imagem baixada encontrada para recortar.")
        else:
            media_id_manual = st.number_input("Insira o ID da Mídia do WP", min_value=0, step=1, value=0)
            st.info("O ID inserido será vinculado diretamente ao post no WordPress.")
            st.session_state.cropped_img = None

    # Botão de Execução de rotina de API
    if st.button("Publicar Rest API no WordPress"):
        if not (wp_url and wp_user and wp_pass):
            st.warning("Preencha todas as credenciais do WordPress.")
        else:
            with st.spinner("Enviando dados via API REST para o WordPress..."):
                try:
                    media_id = None
                    # 1. Fluxo de Obtenção da Imagem Destacada
                    if mode_destaque == "Informar ID de mídia fixa (WP)":
                        if media_id_manual > 0:
                            media_id = int(media_id_manual)
                            st.info(f"Usando ID de mídia existente: {media_id}")
                        else:
                            st.warning("Nenhum ID de mídia válido informado. O post será criado sem imagem destacada.")
                    
                    elif st.session_state.cropped_img:
                        st.info("Fazendo upload da imagem recortada...")
                        # Converter a imagem PIL para bytes
                        img_byte_arr = io.BytesIO()
                        st.session_state.cropped_img.save(img_byte_arr, format='JPEG')
                        img_bytes = img_byte_arr.getvalue()
                        
                        filename = f"cropped_{st.session_state.shortcode}.jpg"
                        headers = {
                            "Content-Disposition": f'attachment; filename="{filename}"',
                            "Content-Type": "image/jpeg"
                        }
                        
                        res_media = requests.post(
                            f"{wp_url.rstrip('/')}/wp-json/wp/v2/media",
                            headers=headers,
                            auth=HTTPBasicAuth(wp_user, wp_pass),
                            data=img_bytes
                        )
                        
                        if res_media.status_code in [200, 201]:
                            media_id = res_media.json().get('id')
                            st.success("Mídia recortada enviada com sucesso!")
                        else:
                            st.error(f"Erro no upload da mídia: HTTP {res_media.status_code} - {res_media.text}")
                    
                    # 2. Fluxo de Criação do Post
                    st.info("Criando a postagem...")
                    
                    # Embala tags <p> em blocos Gutenberg nativos apenas no momento do envio
                    gutenberg_content = edited_content.replace("<p>", "<!-- wp:paragraph -->\n<p>").replace("</p>", "</p>\n<!-- /wp:paragraph -->")
                    
                    post_payload = {
                        "title": post_title,
                        "content": gutenberg_content,
                        "status": wp_status,
                    }
                    
                    # Adicionando categorias selecionadas
                    if selected_cats:
                        post_payload["categories"] = [cat_options[name] for name in selected_cats]
                            
                    # Processando Tags (Selecionadas + Novas)
                    final_tags = []
                    if selected_tags:
                        final_tags.extend([tag_options[name] for name in selected_tags])
                    
                    if extra_tags_input:
                        new_tag_names = [t.strip() for t in extra_tags_input.split(',') if t.strip()]
                        for tname in new_tag_names:
                            # Tenta encontrar no que já foi baixado (cache)
                            found_id = None
                            for existing_name, existing_id in tag_options.items():
                                if existing_name.lower() == tname.lower():
                                    found_id = existing_id
                                    break
                            
                            if found_id:
                                if found_id not in final_tags:
                                    final_tags.append(found_id)
                            else:
                                # Cria nova tag no WP
                                st.info(f"Criando nova tag: {tname}...")
                                res_new_tag = requests.post(
                                    f"{wp_url.rstrip('/')}/wp-json/wp/v2/tags",
                                    auth=HTTPBasicAuth(wp_user, wp_pass),
                                    json={"name": tname}
                                )
                                if res_new_tag.status_code in [200, 201]:
                                    final_tags.append(res_new_tag.json().get('id'))
                                elif res_new_tag.status_code == 400:
                                    # Se já existe mas não estava no cache, o WP as vezes não retorna o ID
                                    # Vamos apenas logar o erro por enquanto ou tentar buscar
                                    st.warning(f"Não foi possível criar/vincular a tag '{tname}'. Verifique se ela já existe com outro slug.")
                    
                    if final_tags:
                        post_payload["tags"] = final_tags
                    if media_id:
                        post_payload["featured_media"] = media_id
                        
                    res_post = requests.post(
                        f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts",
                        auth=HTTPBasicAuth(wp_user, wp_pass),
                        json=post_payload
                    )
                    
                    if res_post.status_code in [200, 201]:
                        post_json = res_post.json()
                        st.success(f"Post {post_json.get('id')} criado com sucesso!")
                        st.markdown(f"**[Clique aqui para Acessar/Ver o Post]({post_json.get('link')})**")
                    else:
                        st.error(f"Erro ao criar postagem: {res_post.status_code} - {res_post.text}")
                        
                except Exception as e:
                    st.error(f"Erro de comunicação: {str(e)}")
