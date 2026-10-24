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

if st.button("🚀 Mulai Proses Video", type="primary"):
    if not api_key:
        st.error("Silakan masukkan Gemini API Key terlebih dahulu di sidebar!")
    elif not youtube_url:
        st.error("Silakan masukkan link YouTube!")
    else:
        try:
            client = genai.Client(api_key=api_key)
            
            with st.status("📥 Mengambil metadata dan transkrip video...", expanded=True) as status:
                
                # Gunakan parameter universal agar aman membaca info dasar video dari server mana pun
                ydl_opts = {
                    'extract_flat': False,
                    'skip_download': True,
                    'writesubtitles': True,
                    'writeautomaticsubtext': True,
                    'quiet': True,
                    'no_warnings': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
                
                # SISTEM RETRY AGRESIF (MENGATASI ERROR JIKA SERVER GOOGLE PADAT)
                response = None
                max_retries = 5
                wait_time = 5
                
                for attempt in range(max_retries):
                    try:
                        response = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=prompt
                        )
                        break
                    except Exception as ai_err:
                        if "503" in str(ai_err) and attempt < max_retries - 1:
                            st.warning(f"Server Google Gemini sedang sibuk. Mencoba kembali dalam {wait_time} detik... ({attempt+1}/{max_retries})")
                            time.sleep(wait_time)
                            wait_time += 3
                        else:
                            raise ai_err
                
                res_data = json.loads(clean_json_response(response.text))
                
                st.write("✨ Momen FYP Direkomendasikan!")
                st.info(f"**Alasan Pilihan AI:** {res_data['reason']}")
                st.metric("Target Potongan Waktu", f"{res_data['start_time']} - {res_data['end_time']}")
                
                status.update(label="🎬 Mengekstrak streaming langsung & melakukan Center Crop (9:16)...", state="running")
                
                # UPDATE: Menggunakan format universal 'bestvideo+bestaudio/best' untuk stabilitas ekstra di Cloud
                with yt_dlp.YoutubeDL({'format': 'bestvideo+bestaudio/best', 'quiet': True, 'no_warnings': True}) as ydl:
                    real_info = ydl.extract_info(youtube_url, download=False)
                    # Menangani format jika video dan audio terpisah (Dapatkan URL masing-masing komponen)
                    if 'requested_formats' in real_info:
                        video_url = real_info['requested_formats'][0]['url']
                        audio_url = real_info['requested_formats'][1]['url']
                        
                        ffmpeg_cmd = [
                            'ffmpeg',
                            '-ss', res_data['start_time'], '-to', res_data['end_time'], '-i', video_url,
                            '-ss', res_data['start_time'], '-to', res_data['end_time'], '-i', audio_url,
                            '-vf', "crop=ih*(9/16):ih",
                            '-c:v', 'libx264', '-preset', 'veryfast',
                            '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
                            '-y', "fyp_clip.mp4"
                        ]
                    else:
                        # Jika kebetulan format gabungan langsung tersedia
                        stream_url = real_info['url']
                        ffmpeg_cmd = [
                            'ffmpeg',
                            '-ss', res_data['start_time'], '-to', res_data['end_time'], '-i', stream_url,
                            '-vf', "crop=ih*(9/16):ih",
                            '-c:v', 'libx264', '-preset', 'veryfast',
                            '-c:a', 'aac',
                            '-y', "fyp_clip.mp4"
                        ]
                
                output_filename = "fyp_clip.mp4"
                if os.path.exists(output_filename):
                    try: os.remove(output_filename)
                    except: pass
                
                # Jalankan perintah perakitan klip video vertikal
                subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                status.update(label="🎉 Klip video FYP Anda siap!", state="complete")
            
            # Tampilkan Hasil Akhir di Halaman Web
            st.balloons()
            col1, col2 = st.columns(2)
            
            with col1:
                st.success("### 📝 Metadata Buatan Gemini")
                st.markdown(f"**Judul Konten:**\n```\n{res_data['title']}\n```")
                st.markdown(f"**Deskripsi & Tag:**\n```\n{res_data['description']}\n```")
            
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
            st.error(f"Terjadi kesalahan teknis: {str(e)}\n\nTips: Silakan tunggu beberapa saat lalu coba klik kembali tombol 'Mulai Proses Video'.")
