// Web Audio API Synthesizer for High-Priority Trading Alerts

class SoundEngine {
  private ctx: AudioContext | null = null;
  private enabled: boolean = true;

  constructor() {
    // Lazy audio context init upon first user interaction
  }

  private getContext(): AudioContext | null {
    if (!this.enabled) return null;
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
    return this.ctx;
  }

  public setEnabled(val: boolean) {
    this.enabled = val;
  }

  public isEnabled(): boolean {
    return this.enabled;
  }

  public playTone(freq: number, duration: number, delay: number = 0, type: OscillatorType = 'sine') {
    const ctx = this.getContext();
    if (!ctx) return;

    setTimeout(() => {
      try {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = type;
        osc.frequency.setValueAtTime(freq, ctx.currentTime);

        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start();
        osc.stop(ctx.currentTime + duration);
      } catch (e) {
        console.warn('Audio play failed:', e);
      }
    }, delay * 1000);
  }

  public playSignalAlert() {
    // Upward high-conviction chime
    this.playTone(523.25, 0.2, 0.0); // C5
    this.playTone(659.25, 0.2, 0.15); // E5
    this.playTone(783.99, 0.4, 0.3); // G5
  }

  public playBreakevenAlert() {
    // Two fast bell rings (cost protection)
    this.playTone(880, 0.15, 0.0);
    this.playTone(1046.5, 0.35, 0.12);
  }

  public playTargetHitAlert() {
    // Triumphant profit target reached
    this.playTone(523.25, 0.15, 0.0);
    this.playTone(659.25, 0.15, 0.12);
    this.playTone(783.99, 0.15, 0.24);
    this.playTone(1046.50, 0.5, 0.36);
  }

  public playReversalAlert() {
    // Warning tone
    this.playTone(698.46, 0.2, 0.0, 'triangle');
    this.playTone(554.37, 0.35, 0.18, 'triangle');
  }

  public playStopLossAlert() {
    // Low alarm tone
    this.playTone(440, 0.25, 0.0, 'sawtooth');
    this.playTone(330, 0.4, 0.2, 'sawtooth');
  }
}

export const soundEngine = new SoundEngine();

