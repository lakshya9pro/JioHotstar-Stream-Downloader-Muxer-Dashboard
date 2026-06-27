import os
import subprocess
import sys

def parse_url_file(filepath):
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return None, {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines()]
    
    headers = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        # Match keys that start with ':' (pseudo headers) or standard headers where key is followed by value
        if line.startswith(':') or (line and not line.startswith('http') and i + 1 < len(lines) and lines[i+1]):
            key = line
            val = lines[i+1]
            headers[key.lower()] = val
            i += 2
        else:
            i += 1
            
    # Try to extract or reconstruct the manifest URL
    url = ""
    
    # 1. Check if there's any line that is a full URL containing .mpd, .m3u8, or /videos/
    for line in lines:
        if (line.startswith("http://") or line.startswith("https://")) and (".mpd" in line or ".m3u8" in line or "/videos/" in line):
            url = line
            break
            
    # 2. Reconstruct from HTTP/2 pseudo-headers (:scheme, :authority, :path)
    if not url:
        scheme = headers.get(":scheme", "https")
        authority = headers.get(":authority")
        path = headers.get(":path")
        if authority and path:
            url = f"{scheme}://{authority}{path}"
            
    # 3. Fallback: Search for any full URL that is NOT the Referer or Origin
    if not url:
        referer_val = headers.get("referer", "").strip()
        origin_val = headers.get("origin", "").strip()
        for line in lines:
            if line.startswith("http://") or line.startswith("https://"):
                if line != referer_val and line != origin_val:
                    url = line
                    break
                    
    # 4. Ultimate Fallback: The first line starting with http
    if not url:
        for line in lines:
            if line.startswith("http://") or line.startswith("https://"):
                url = line
                break
                
    return url, headers

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--quality', default='best')
    parser.add_argument('--audio-langs', default='')
    parser.add_argument('--sub-langs', default='')
    parser.add_argument('--mode', default='mux')
    parser.add_argument('--embed-subs', default='true')
    parser.add_argument('--embed-metadata', default='true')
    parser.add_argument('--output-name', default='hotstar_video')
    args = parser.parse_args()

    filepath = "url.txt"
    url, headers = parse_url_file(filepath)
    if not url:
        print("Error: Could not detect or reconstruct the video URL from url.txt.")
        return
        
    cookie = headers.get("cookie", "")
    user_agent = headers.get("user-agent", "")
    referer = headers.get("referer", "https://www.hotstar.com/")
    origin = headers.get("origin", "https://www.hotstar.com")
    
    print("--- Parsed Information ---")
    print(f"URL: {url[:100]}...")
    print(f"User-Agent: {user_agent}")
    print(f"Cookie (len): {len(cookie)} chars")
    print(f"Referer: {referer}")
    print(f"Selected Quality: {args.quality}")
    print(f"Selected Audio Languages: {args.audio_langs or 'default'}")
    print(f"Selected Subtitle Languages: {args.sub_langs or 'default'}")
    print(f"Download Mode: {args.mode}")
    print("--------------------------\n")
    
    # Video format selection
    video_fmt = "bv*"
    if args.quality and args.quality != 'best':
        height = args.quality.replace('p', '')
        if height.isdigit():
            video_fmt = f"bv*[height={height}]"
            
    # Audio format selection
    audio_fmt = ""
    if args.audio_langs:
        langs = [l.strip() for l in args.audio_langs.split(',') if l.strip()]
        if 'all' in langs:
            audio_fmt = "mergeall[vcodec=none]"
        elif 'none' in langs:
            audio_fmt = ""
        else:
            if args.mode == 'mux':
                audio_fmt = "+".join(f"ba[language={l}]" for l in langs)
            else:
                audio_fmt = ",".join(f"ba[language={l}]" for l in langs)
    else:
        # Default to best audio if nothing selected
        audio_fmt = "ba"
        
    # Combine video and audio
    if audio_fmt:
        if args.mode == 'mux':
            format_str = f"{video_fmt}+{audio_fmt}"
        else:
            format_str = f"{video_fmt},{audio_fmt}"
    else:
        format_str = video_fmt
        
    # Construct the yt-dlp command
    cmd = ["yt-dlp", url, "-f", format_str]
    
    # Flags to download subtitles
    if args.sub_langs and args.sub_langs != 'none':
        cmd.append("--write-subs")
        sub_langs_list = [s.strip() for s in args.sub_langs.split(',') if s.strip()]
        if 'all' in sub_langs_list:
            cmd.extend(["--sub-langs", "all"])
        else:
            cmd.extend(["--sub-langs", ",".join(sub_langs_list)])
            
        if args.mode == 'mux' and args.embed_subs == 'true':
            cmd.append("--embed-subs")
            
    if args.embed_metadata == 'true':
        cmd.append("--embed-metadata")
        
    if args.mode == 'mux' and audio_fmt:
        cmd.append("--audio-multistreams")
        
    # Add cookies & headers
    if user_agent:
        cmd.extend(["--user-agent", user_agent])
    if cookie:
        cmd.extend(["--add-header", f"Cookie: {cookie}"])
    if referer:
        cmd.extend(["--add-header", f"Referer: {referer}"])
    if origin:
        cmd.extend(["--add-header", f"Origin: {origin}"])
        
    # Output template
    if args.mode == 'mux':
        cmd.extend(["-o", f"{args.output_name}.mkv"])
    else:
        # Use a template that keeps format IDs to avoid overwrite
        cmd.extend(["-o", f"{args.output_name}.%(format_id)s.%(ext)s"])
        
    print("Constructed Command:")
    print(" ".join(f'"{arg}"' if " " in arg or "=" in arg or ";" in arg or "&" in arg or "?" in arg else arg for arg in cmd))
    print("\nRunning yt-dlp...")
    
    try:
        subprocess.run(cmd, check=True)
        print("\nDownload finished successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\nError occurred during yt-dlp execution: {e}")
    except FileNotFoundError:
        print("\nError: yt-dlp was not found in your system's PATH.")


if __name__ == "__main__":
    main()
