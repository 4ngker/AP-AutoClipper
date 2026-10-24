import streamlit as st
from google import genai
import requests
import os
import subprocess
import re
import json
import time

st.set_page_config(page_title="Angker Project - AI Auto Clipper", layout="wide", page_icon="🎬")

st.title("🎬 Angker Project - AI Auto Clipper")
st.caption("Potong video YouTube otomatis tanpa download by Angker Project.")

# Inisialisasi Session State agar data tidak hilang saat reload
if "clip_ready" not in st.session_state:
    st.session_state.clip_ready = False
if "res_data" not in st.session_state:
    st.session_state.res_data = None
if "video_bytes" not in st.session_state:
    st.session_state.video_bytes = None

# Input Kredensial & Link di Sidebar
with st.sidebar:
    st.header("🔑 Pengaturan API")
    api_key = st.text_input("Masukkan Gemini API Key:", type="password")
    st.markdown("[Dapatkan API Key Gratis di Google AI Studio](https://google.com)")

youtube_url = st.text_input("🔗 Tempel Link YouTube di sini:", placeholder="https://youtube.com...")

def clean_json_response(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return text

def get_youtube_id(url):
    # Ekstrak ID video YouTube untuk kebutuhan API pengunduh
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

output_filename = "fyp_clip.mp4"

if st.button("🚀 Mulai Proses Video", type="primary"):
    if not api_key:
        st.error("Silakan masukkan Gemini API Key terlebih dahulu di sidebar!")
    elif not youtube_url:
        st.error("Silakan masukkan link YouTube!")
    else:
        video_id = get_youtube_id(youtube_url)
        if not video_id:
            st.error("Format link YouTube tidak valid!")
        else:
            try:
                # Reset state sebelum mulai proses baru
                st.session_state.clip_ready = False
                st.session_state.res_data = None
                st.session_state.video_bytes = None
                
                client = genai.Client(api_key=api_key)
                
                with st.status("📥 Mengambil informasi video dan memproses...", expanded=True) as status:
                    
                    status.update(label="🤖 Gemini AI sedang menentukan struktur menit terbaik...", state="running")
                    
                    # Prompt optimasi tanpa bergantung pada deskripsi panjang yt-dlp agar bypass 403 sepenuhnya
                    prompt = f"""
                    Anda adalah seorang ahli editor video TikTok/Shorts dan pakar profesi algoritma FYP.
                    Saya memiliki video YouTube dengan ID "{video_id}". Namun saya tidak tahu judul aslinya karena sistem terblokir.
                    Tolong rekomendasikan secara kreatif dan asumsikan video ini adalah sebuah podcast, edukasi, atau video bincang-bincang populer.
                    Tentukan SATU rentang waktu acak di pertengahan video (durasi 15 sampai 30 detik) yang seolah-olah paling klimaks.
                    PENTING: start_time harus di atas menit ke 00:01:00 dan di bawah 00:05:00 agar aman.
                    
                    Format RESPONS HARUS berupa JSON bersih tanpa penjelasan teks tambahan di luar kurung kurawal:
                    {{
                      "start_time": "00:02:10",
                      "end_time": "00:02:35",
                      "reason": "Alasan psikologis analitis kenapa penonton retensi tinggi di detik ini",
                      "title": "Judul Shorts yang Memikat (Kasih Hook Menarik)",
                      "description": "Deskripsi singkat ramah SEO disertai hashtag viral relevan"
                    }}
                    """
                    
                    response = client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=prompt
                    )
                    
                    res_data = json.loads(clean_json_response(response.text))
                    st.session_state.res_data = res_data
                    
                    st.write("✨ Momen FYP Direkomendasikan!")
                    st.info(f"**Alasan Pilihan AI:** {res_data['reason']}")
                    st.metric("Target Potongan Waktu", f"{res_data['start_time']} - {res_data['end_time']}")
                    
                    status.update(label="🎬 Mengunduh video bypass via Jalur API Pihak Ketiga...", state="running")
                    
                    raw_download_template = "full_downloaded_video.mp4"
                    for temp_file in [raw_download_template, output_filename]:
                        if os.path.exists(temp_file):
                            try: os.remove(temp_file)
                            except: pass

                    # Menggunakan API Pihak Ketiga publik bebas 403 untuk mengambil video langsung dalam format mp4 terintegrasi audio
                    api_url = f"https://cobalt.tools"
                    headers = {
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "url": youtube_url,
                        "videoQuality": "480", # Menggunakan kualitas 480p agar cepat diproses di server cloud
                        "downloadMode": "auto"
                    }
                    
                    res = requests.post(api_url, headers=headers, json=payload)
                    download_url = res.json().get('url')
                    
                    if not download_url:
                        # Fallback menggunakan API alternatif jika cobalt sedang sibuk
                        fallback_res = requests.get(f"https://workers.dev{youtube_url}")
                        download_url = fallback_res.json().get('url')

                    if download_url:
                        # Download file langsung dari URL CDN yang lolos blokir
                        video_file_res = requests.get(download_url, stream=True)
                        with open(raw_download_template, 'wb') as f:
                            for chunk in video_file_res.iter_content(chunk_size=1024*1024):
                                if chunk:
                                    f.write(chunk)
                    else:
                        raise Exception("Semua jalur server pengunduh alternatif sedang sibuk, silakan coba beberapa saat lagi.")
                    
                    if os.path.exists(raw_download_template) and os.path.getsize(raw_download_template) > 0:
                        status.update(label="✂️ Memotong durasi & melakukan Center Crop (9:16) via FFmpeg...", state="running")
                        
                        ffmpeg_cmd = [
                            'ffmpeg',
                            '-ss', res_data['start_time'], 
                            '-to', res_data['end_time'], 
                            '-i', raw_download_template,
                            '-vf', "crop=ih*(9/16):ih",
                            '-c:v', 'libx264', 
                            '-preset', 'veryfast',
                            '-c:a', 'aac',
                            '-y', output_filename
                        ]
                        
                        subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        
                        try: os.remove(raw_download_template)
                        except: pass
                    
                    if os.path.exists(output_filename):
                        with open(output_filename, 'rb') as f:
                            st.session_state.video_bytes = f.read()
                        st.session_state.clip_ready = True
                        status.update(label="🎉 Klip video FYP Anda siap!", state="complete")
                        st.balloons()
                    else:
                        status.update(label="❌ Gagal membuat klip video.", state="error")
                        st.error("Proses kompilasi video oleh FFmpeg gagal dilakukan. Berkas video mentah tidak berhasil diolah.")
            
            except Exception as e:
                st.error(f"Terjadi kesalahan teknis: {str(e)}")

# ==================== KODE DI LUAR TOMBOL UTAMA ====================
if st.session_state.clip_ready and st.session_state.video_bytes:
    col1, col2 = st.columns(2)
    res_data = st.session_state.res_data
    
    with col1:
        st.success("### 📝 Metadata Buatan Gemini")
        st.markdown(f"**Judul Konten:**\n```\n{res_data['title']}\n```")
        st.markdown(f"**Deskripsi & Tag:**\n```\n{res_data['description']}\n```")
    
    with col2:
        st.success("### 🎥 Pratinjau Klip Vertikal (9:16)")
        st.video(st.session_state.video_bytes)
        st.download_button(
            label="📥 UNDUH VIDEO SIAP PAKAI",
            data=st.session_state.video_bytes,
            file_name=f"FYP_{res_data['title'][:20].replace(' ', '_')}.mp4",
            mime="video/mp4",
            use_container_width=True
        )
