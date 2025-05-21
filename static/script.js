// 背景画像をランダムに設定（画像は background_img フォルダに保存）
// 必要に応じてファイル名を増やしてください
const bgImages = [
  "bg1.png",
  "bg2.png",
  "bg3.png"
];

const randomBg = bgImages[Math.floor(Math.random() * bgImages.length)];
document.body.style.backgroundImage = `url('/static/background_img/${randomBg}')`;

// 画像選択時にプレビュー表示（送信処理は止めない！）
document.getElementById("imageInput").addEventListener("change", function () {
  const file = this.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function (event) {
    const img = document.getElementById("preview-image");
    img.src = event.target.result;
    document.getElementById("preview-section").classList.remove("d-none");
  };
  reader.readAsDataURL(file);
});
