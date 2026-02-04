import numpy as np
import matplotlib.pyplot as plt
import librosa
import librosa.display
import seaborn as sns
from scipy.signal import welch
from scipy.stats import f_oneway
import os

def run_stable_analysis(file_path, minutes=10, start_offset_minutes=10):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    duration_to_load = minutes * 60
    start_offset_seconds = start_offset_minutes * 60
    print(f"Loading {minutes} minutes of {file_path} starting at minute {start_offset_minutes}...")
    
    # Use duration to prevent memory overload
    y, sr = librosa.load(
        file_path,
        sr=None,
        duration=duration_to_load,
        offset=start_offset_seconds,
    )
    
    # 1. SPECTROGRAM
    print("Generating Spectrogram...")
    plt.figure(figsize=(12, 6))
    # Using a larger hop_length to save memory during plotting
    D = librosa.amplitude_to_db(np.abs(librosa.stft(y, hop_length=1024)), ref=np.max)
    librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='hz', cmap='magma', hop_length=1024)
    sns.despine(offset=10)
    plt.colorbar(format='%+2.0f dB')
    plt.title(f'Analysis 1: Spectrogram (Minutes {start_offset_minutes}-{start_offset_minutes + minutes})', fontsize=20)
    plt.xlabel('Time (s)', fontsize=20)
    plt.ylabel('Frequency (Hz)', fontsize=20)
    plt.ylim(0, 22000)
    plt.tight_layout()
    plt.tick_params(axis='both', which='major', labelsize=20)
    plt.savefig('1_spectrogram.png', transparent=True, dpi=300, bbox_inches='tight')
    plt.savefig('1_spectrogram.svg', transparent=True, dpi=300, bbox_inches='tight')
    plt.close()

    # 2. SPECTRAL STATIONARITY
    print("Analyzing Spectral Stationarity...")
    plt.figure(figsize=(10, 6))
    num_segs = 4
    seg_samples = len(y) // num_segs
    psd_list = []
    
    for i in range(num_segs):
        start = i * seg_samples
        end = start + seg_samples
        # nperseg=8192 gives high frequency resolution
        freqs, psd = welch(y[start:end], sr, nperseg=8192)
        psd_list.append(psd)
        seg_start_min = start_offset_minutes + i * (minutes / num_segs)
        plt.semilogy(freqs, psd, label=f'Segment {i+1} ({seg_start_min:.1f} min)', alpha=0.7)
    
    # Calculate variance and significance
    psd_array = np.array(psd_list)
    variance_across_segs = np.var(psd_array, axis=0)
    mean_variance = np.mean(variance_across_segs)
    
    # ANOVA test for statistical significance
    f_stat, p_value = f_oneway(*psd_list)
    
    plt.title('Analysis 2: Power Spectral Density (Consistency Check)', fontsize=20)
    plt.xlabel('Frequency (Hz)', fontsize=20)
    plt.ylabel('Power', fontsize=20)
    plt.legend(fontsize=12)
    plt.grid(True, which='both', alpha=0.3)
    plt.xlim(0, 22000)
    plt.tight_layout()
    plt.tick_params(axis='both', which='major', labelsize=20)
    sns.despine(offset=10)
    plt.savefig('2_spectral_stability.png', transparent=True, dpi=300, bbox_inches='tight')
    plt.savefig('2_spectral_stability.svg', transparent=True, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"\n  Overall Variance across segments (mean): {mean_variance:.6e}")
    print(f"  ANOVA F-statistic: {f_stat:.4f}")
    print(f"  ANOVA p-value: {p_value:.6e}")
    print(f"  → Spectral stability: {'STABLE (no significant variation)' if p_value >= 0.05 else 'UNSTABLE (significant variation)'}")
    
    # Per-frequency variance analysis
    print(f"\n  Per-Frequency Variance (Top 5 most variable frequencies):")
    top_freq_indices = np.argsort(variance_across_segs)[-5:][::-1]
    for idx in top_freq_indices:
        freq = freqs[idx]
        var = variance_across_segs[idx]
        print(f"    {freq:.0f} Hz: variance = {var:.6e}")
    
    # Per-segment statistics
    print(f"\n  Per-Segment Mean Power:")
    for i, psd in enumerate(psd_list):
        seg_start_min = start_offset_minutes + i * (minutes / num_segs)
        mean_power = np.mean(psd)
        print(f"    Segment {i+1} ({seg_start_min:.1f} min): {mean_power:.6e}")

    # 3. RMS VOLUME
    print("Analyzing RMS Volume...")
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr) + start_offset_seconds
    plt.figure(figsize=(12, 4))
    plt.plot(times, rms, color='blue', alpha=0.5)
    plt.title('Analysis 3: Volume Envelope (Looking for repetitive cues)', fontsize=20)
    plt.xlabel('Time (s)', fontsize=20)
    plt.ylabel('RMS Amplitude', fontsize=20)
    plt.tight_layout()
    plt.tick_params(axis='both', which='major', labelsize=20)
    sns.despine(offset=10)
    plt.savefig('3_amplitude_envelope.png', transparent=True, dpi=300, bbox_inches='tight')
    plt.savefig('3_amplitude_envelope.svg', transparent=True, dpi=300, bbox_inches='tight')
    plt.close()

    print(
        f"\nSUCCESS: Images saved. Analyzing {minutes} minutes starting at minute "
        f"{start_offset_minutes} used {y.nbytes / 1e6:.2f} MB of RAM."
    )

if __name__ == "__main__":
    FILENAME = "session_noise.wav" 
    run_stable_analysis(FILENAME, minutes=10)