import streamlit as st
from google import genai
import yt_dlp
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

output_filename = "fyp_clip.mp4"

if st.button("🚀 Mulai Proses Video", type="primary"):
    if not api_key:
        st.error("Silakan masukkan Gemini API Key terlebih dahulu di sidebar!")
    elif not youtube_url:
        st.error("Silakan masukkan link YouTube!")
    else:
        try:
            # Reset state sebelum mulai proses baru
            st.session_state.clip_ready = False
            st.session_state.res_data = None
            st.session_state.video_bytes = None
            
            client = genai.Client(api_key=api_key)
            
            with st.status("📥 Mengambil metadata video...", expanded=True) as status:
                
                # Opsi ekstra yt-dlp dengan User-Agent agar lolos blokir deteksi awal
                ydl_opts_meta = {
                    'extract_flat': False,
                    'skip_download': True,
                    'quiet': True,
                    'no_warnings': True,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                    }
                }
                
                with yt_dlp.YoutubeDL(ydl_opts_meta) as ydl:
                    info = ydl.extract_info(youtube_url, download=False)
                    video_title = info.get('title', 'Video')
                    video_description = info.get('description', '')
                    duration = info.get('duration', 0)
                
                status.update(label="🤖 Gemini AI sedang menganalisis struktur menit terbaik...", state="running")
                st.write(f"Menganalisis video: **{video_title}**")
                
                prompt = f"""
                Anda adalah seorang ahli editor video TikTok/Shorts dan pakar profesi algoritma FYP.
                Saya memiliki video YouTube berjudul "{video_title}" dengan durasi total {duration} detik.
                Deskripsi video: {video_description[:1000]}

                Tugas Anda: Berdasarkan data di atas, tentukan SATU rentang waktu (durasi 15 sampai 45 detik) yang paling klimaks, kontroversial, atau menarik untuk dijadikan video Shorts vertikal. Rentang waktu tidak boleh melebihi durasi total video ({duration} detik).
                
                Format RESPONS HARUS berupa JSON bersih tanpa penjelasan teks tambahan di luar kurung kurawal:
                {{
                  "start_time": "00:01:10",
                  "end_time": "00:01:45",
                  "reason": "Alasan detail kenapa momen menit ini yang dipilih untuk FYP",
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
                
                status.update(label="🎬 Mengunduh klip dasar dengan menyamar sebagai Browser...", state="running")
                
                raw_download_template = "full_downloaded_video.mp4"
                
                # PERBAIKAN MANIFES: Menambahkan header penyamaran lengkap agar bypass HTTP 403 & 502
                ydl_opts_download = {
                    'format': 'bestvideo+bestaudio/best',
                    'format_sort': ['vcodec:h264', 'res:480', 'acodec:aac'], # Batasi ke 480p agar download sangat cepat di cloud
                    'merge_output_format': 'mp4',
                    'outtmpl': raw_download_template,
                    'quiet': True,
                    'no_warnings': True,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Sec-Fetch-Mode': 'navigate'
                    }
                }
                
                # Bersihkan sisa file proses sebelumnya jika masih ada
                for temp_file in [raw_download_template, output_filename]:
                    if os.path.exists(temp_file):
                        try: os.remove(temp_file)
                        except: pass
                
                with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                    ydl.download([youtube_url])
                
                if os.path.exists(raw_download_template):
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
