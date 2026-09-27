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
  revision 1

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

    # Where zsh looks with no setup, so Tab completion works on the next shell.
    zsh_completion.install "completions/_cinta"

    install_models libexec/"models"

    # cintarec is an implementation detail, kept off PATH in libexec. The
    # models live inside the keg too, so uninstalling removes them with the rest.
    (bin/"cinta").write_env_script libexec/"bin/cinta",
      CINTA_RECORDER:   libexec/"cintarec",
      CINTA_MODELS_DIR: libexec/"models"
  end

  # The Whisper models, fetched during install so that the first transcription
  # needs nothing. Not resources: Homebrew keeps a second copy of every
  # resource in its download cache, 3 GB that would outlive the install.
  def models
    {
      "ggml-large-v3.bin"      => [
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
        "64d182b440b98d5203c4f9bd541544d84c605196c4f7b845dfa11fb23594d1e2",
        "speech recognition model",
        "3.1 GB, a few minutes",
      ],
      "ggml-silero-v5.1.2.bin" => [
        "https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin",
        "29940d98d42b91fbd05ce489f3ecf7c72f0a42f027e4875919a28fb4c04ea2cf",
        "voice activity model",
        "885 KB",
      ],
    }
  end

  def install_models(directory)
    directory.mkpath
    models.each do |name, (url, sha256, what, size)|
      target = directory/name

      # On upgrade the installed version is still in the Cellar. A hard link to
      # its copy is instant and takes no space, and the file outlives the old
      # keg when Homebrew removes it.
      previous = Pathname.glob(HOMEBREW_CELLAR/"cinta/*/libexec/models/#{name}")
                         .find { |path| path.sha256 == sha256 }
      if previous
        ohai "Keeping the Whisper #{what} from the installed version"
        File.link previous, target
        next
      end

      ohai "Downloading the Whisper #{what} (#{size})"
      system "curl", "--fail", "--silent", "--show-error", "--location", "--output", target, url
      odie "#{name} does not match its checksum" if target.sha256 != sha256
    end
  end

  def caveats
    <<~EOS
      Screen recording: macOS grants the permission to your terminal, not to
      cinta. System Settings > Privacy & Security > Screen & System Audio
      Recording, enable your terminal, then restart it.
    EOS
  end

  test do
    assert_equal "cinta #{version}", shell_output("#{bin}/cinta --version").strip
    assert_equal version.to_s, shell_output("#{libexec}/cintarec --version").strip
    assert_match "transcribe", shell_output("#{bin}/cinta --help")
    assert_path_exists zsh_completion/"_cinta"
    # Exit code 20 is cintarec rejecting its arguments, which it does before
    # asking macOS for any permission, so this runs anywhere.
    shell_output("#{libexec}/cintarec --fps 0 --output #{testpath}/x.mov 2>&1", 20)
  end
end
