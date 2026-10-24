import streamlit as st
from google import genai
import yt_dlp
import os
import subprocess
import re
import json

st.set_page_config(page_title="Angker Project - AI Auto Clipper", layout="wide", page_icon="🎬")

st.title("🎬 Angker Project - AI Auto Clipper")
st.caption("Potong video YouTube otomatis format FYP (9:16) langsung di Cloud memanfaatkan Gemini 2.5 Flash.")

# Input Kredensial & Link
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

if st.button("🚀 Mulai Proses Video", type="primary"):
    if not api_key:
        st.error("Silakan masukkan Gemini API Key terlebih dahulu di sidebar!")
    elif not youtube_url:
        st.error("Silakan masukkan link YouTube!")
    else:
        try:
            client = genai.Client(api_key=api_key)
            
            with st.status("📥 Mengekstrak informasi dan audio video...", expanded=True) as status:
                # 1. Unduh audio resolusi rendah menggunakan yt-dlp untuk dianalisis Gemini
                ydl_opts = {
                    'format': 'worst/mp4',
                    'outtmpl': 'temp_low_res.mp4',
                    'overwrites': True
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=True)
                    video_title = info.get('title', 'Video')
                
                status.update(label="🤖 Gemini AI sedang mencari momen FYP terbaik...", state="running")
                
                # 2. Upload ke Gemini untuk analisis media
                st.write("Mengunggah sampel ke Gemini API...")
                media_file = client.files.upload(file="temp_low_res.mp4")
                
                prompt = """
                Analisis video ini dan pilih satu momen berdurasi 15-45 detik yang paling menarik, emosional, atau berpotensi viral (FYP).
                Berikan respon HARUS dalam format JSON bersih seperti ini tanpa penjelasan teks lain:
                {
                  "start_time": "00:01:20",
                  "end_time": "00:01:50",
                  "reason": "Alasan kenapa momen ini viral",
                  "title": "Judul Shorts/TikTok yang Menarik (pake Hook)",
                  "description": "Deskripsi lengkap dan hashtag relevan"
                }
                """
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[media_file, prompt]
                )
                
                # Bersihkan file sampah di cloud setelah upload selesai
                client.files.delete(name=media_file.name)
                if os.path.exists("temp_low_res.mp4"):
                    os.remove("temp_low_res.mp4")
                
                res_data = json.loads(clean_json_response(response.text))
                
                st.write("✨ Momen FYP Berhasil Ditemukan!")
                st.info(f"**Alasan:** {res_data['reason']}")
                
                status.update(label="🎬 Sedang memotong dan mengubah format video jadi Vertikal (9:16)...", state="running")
                
                # 3. Potong video langsung dari server streaming YouTube menggunakan ffmpeg (Tanpa download penuh)
                # Dapatkan URL streaming langsung video asli
                with yt_dlp.YoutubeDL({'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]'}) as ydl:
                    real_info = ydl.extract_info(youtube_url, download=False)
                    stream_url = real_info['url']
                
                output_filename = "fyp_clip.mp4"
                if os.path.exists(output_filename):
                    os.remove(output_filename)
                
                # Perintah FFmpeg tingkat tinggi untuk potong streaming langsung + Crop Vertikal 9:16 tengah
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-ss', res_data['start_time'],
                    '-to', res_data['end_time'],
                    '-i', stream_url,
                    '-vf', "crop=ih*(9/16):ih", # Auto 9:16 Center Crop
                    '-c:v', 'libx264',
                    '-profile:v', 'main',
                    '-level:v', '3.1',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-movflags', '+faststart',
                    '-y', output_filename
                ]
                
                subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                status.update(label="🎉 Klip video siap dipublikasikan!", state="complete")
            
            # Tampilkan Hasil di Web
            st.balloons()
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.success("### 📝 Metadata Buatan Gemini")
                st.markdown(f"**Judul Konten:**\n```\n{res_data['title']}\n```")
                st.markdown(f"**Deskripsi & Tag:**\n```\n{res_data['description']}\n```")
                st.metric("Durasi Potongan", f"{res_data['start_time']} - {res_data['end_time']}")
            
            with col2:
                st.success("### 🎥 Pratinjau Klip Vertikal (9:16)")
                if os.path.exists(output_filename):
                    with open(output_filename, 'rb') as f:
                        video_bytes = f.read()
                    st.video(video_bytes)
                    st.download_button(
                        label="📥 UNDUH VIDEO SIAP PAKAI",
                        data=video_bytes,
                        file_name=f"FYP_{res_data['title'][:20].replace(' ', '_')}.mp4",
                        mime="video/mp4",
                        use_container_width=True
                    )
        
        except Exception as e:
            st.error(f"Terjadi kesalahan teknis: {str(e)}")
