# Written in github.com/alexdlp/cinta at packaging/homebrew/cinta.rb, and
# copied unchanged into github.com/alexdlp/homebrew-tap for each release. Edit
# it in alexdlp/cinta, not in the tap (DESIGN.md 6.4).
class Cinta < Formula
  include Language::Python::Virtualenv

  desc "Record, download and transcribe audio and video from the command-line"
  homepage "https://github.com/alexdlp/cinta"
  url "https://github.com/alexdlp/cinta/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "7b456babd141cb3be7fff59436b03e86caaf10803ad799ea000bfdcd01cf15a3"
  license "MIT"

  depends_on "ffmpeg"
  depends_on macos: :ventura # ScreenCaptureKit with system audio
  depends_on "python@3.14"
  depends_on "whisper.cpp"
  depends_on "yt-dlp"

  # The only resource: cinta has no runtime dependencies, and flit_core, its
  # build backend, has none of its own (DESIGN.md 6.2).
  resource "flit-core" do
    url "https://files.pythonhosted.org/packages/69/59/b6fc2188dfc7ea4f936cd12b49d707f66a1cb7a1d2c16172963534db741b/flit_core-3.12.0.tar.gz"
    sha256 "18f63100d6f94385c6ed57a72073443e1a71a4acb4339491615d0f16d6ff01b2"
  end

  def install
    # Not virtualenv_install_with_resources: that links bin/cinta itself, and
    # bin/cinta has to be the wrapper below.
    venv = virtualenv_create(libexec, "python3.14")
    venv.pip_install resources
    venv.pip_install buildpath

    # SwiftPM's own sandbox cannot nest inside Homebrew's.
    system "swift", "build", "--disable-sandbox", "-c", "release",
           "--package-path", "swift/cintarec"
    libexec.install "swift/cintarec/.build/release/cintarec"

    # cintarec is an implementation detail, kept off PATH in libexec.
    (bin/"cinta").write_env_script libexec/"bin/cinta", CINTA_RECORDER: libexec/"cintarec"
  end

  def caveats
    <<~EOS
      Screen recording: macOS grants the permission to your terminal, not to
      cinta. System Settings > Privacy & Security > Screen & System Audio
      Recording, enable your terminal, then restart it.

      The Whisper models (about 3 GB) are downloaded the first time you
      transcribe something, into ~/cinta/models. Uninstalling cinta leaves them
      and your recordings in place. To remove everything:
        rm -rf ~/cinta ~/.config/cinta
    EOS
  end

  test do
    assert_equal "cinta #{version}", shell_output("#{bin}/cinta --version").strip
    assert_equal version.to_s, shell_output("#{libexec}/cintarec --version").strip
    assert_match "transcribe", shell_output("#{bin}/cinta --help")
    # Exit code 20 is cintarec rejecting its arguments, which it does before
    # asking macOS for any permission, so this runs anywhere.
    shell_output("#{libexec}/cintarec --fps 0 --output #{testpath}/x.mov 2>&1", 20)
  end
end
