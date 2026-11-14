import os
import streamlit as st
import yt_dlp
import whisper
import subprocess

# Set page layout
st.set_page_config(page_title="AI Short Clipper", page_icon="🎬", layout="centered")

st.title("🎬 AI YouTube & Video Auto-Clipper")
st.markdown("Transform long videos or YouTube links into **9:16 vertical shorts** with **automated captions**!")

# --- Input Section ---
input_option = st.radio("Choose input method:", ("YouTube Link", "Upload Video File"))

source_video = None
if input_option == "YouTube Link":
    youtube_url = st.text_input("Paste YouTube URL:")
    if youtube_url:
        with st.spinner("Downloading video from YouTube..."):
            source_video = "downloaded_source.mp4"
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=mp4]/best[ext=mp4]',
                'outtmpl': source_video,
                'forceoverwrites': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])
            st.success("Download complete!")
else:
    uploaded_file = st.file_uploader("Upload an MP4 video file", type=["mp4", "mov", "avi"])
    if uploaded_file is not None:
        source_video = "uploaded_source.mp4"
        with open(source_video, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("File uploaded successfully!")

# --- Clip Timing Configuration ---
st.subheader("⏱️ Define Clip Settings")
col1, col2 = st.columns(2)
with col1:
    start_sec = st.number_input("Start Time (seconds)", min_value=0, value=0)
with col2:
    end_sec = st.number_input("End Time (seconds)", min_value=1, value=30)

# --- Processing Button ---
if source_video and st.button("🚀 Generate Short Clip"):
    if end_sec <= start_sec:
        st.error("End time must be greater than start time.")
    else:
        with st.status("Processing your short...", expanded=True) as status:
            
            # Step 1: Cut specific duration
            st.write("Cutting video segment...")
            clipped_file = "raw_clip.mp4"
            duration = end_sec - start_sec
            subprocess.run([
                'ffmpeg', '-y', '-ss', str(start_sec), '-i', source_video,
                '-t', str(duration), '-c', 'copy', clipped_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            
            # Step 2: Convert to 9:16 Vertical Center Crop
            st.write("Converting to 9:16 vertical layout...")
            vertical_file = "vertical_clip.mp4"
            crop_filter = "crop=ih*(9/16):ih:(iw-ih*(9/16))/2:0"
            subprocess.run([
                'ffmpeg', '-y', '-i', clipped_file, '-vf', crop_filter,
                '-c:a', 'copy', vertical_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            
            # Step 3: Extract Audio & Generate Subtitles with Whisper
            st.write("Transcribing audio and generating captions...")
            audio_file = "temp_audio.mp3"
            subprocess.run([
                'ffmpeg', '-y', '-i', vertical_file, '-q:a', '0', '-map', 'a', audio_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            
            model = whisper.load_model("base")
            result = model.transcribe(audio_file, word_timestamps=True)
            
            # Create SRT file
            srt_path = "subtitles.srt"
            subtitles = []
            index = 1
            for segment in result.get("segments", []):
                if "words" not in segment:
                    continue
                words = segment["words"]
                for i in range(0, len(words), 4):
                    chunk = words[i:i+4]
                    def fmt(s):
                        h, m, sec = int(s//3600), int((s%3600)//60), int(s%60)
                        ms = int((s - int(s)) * 1000)
                        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
                    
                    subtitles.append(f"{index}\n{fmt(chunk[0]['start'])} --> {fmt(chunk[-1]['end'])} \n" + " ".join([w['word'].strip() for w in chunk]) + "\n")
                    index += 1
            
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(subtitles))
                
            # Step 4: Burn Subtitles
            st.write("Burning styled captions onto video...")
            final_output = "final_short.mp4"
            vf_arg = f"subtitles={srt_path}:force_style='FontName=Arial,FontSize=26,PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,BorderStyle=3,Outline=2,Alignment=2,MarginV=60'"
            subprocess.run([
                'ffmpeg', '-y', '-i', vertical_file, '-vf', vf_arg,
                '-c:v', 'libx264', '-crf', '23', '-c:a', 'copy', final_output
            ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            
            status.update(label="✨ Short successfully generated!", state="complete", expanded=False)

        # --- Output & Download ---
        st.subheader("Your Generated Short:")
        st.video(final_output)
        
        with open(final_output, "rb") as file:
            st.download_button(
                label="📥 Download Short MP4",
                data=file,
                file_name="ai_short.mp4",
                mime="video/mp4"
            )
