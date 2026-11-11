img = getArgument();
if (img == "") exit("No image path given");
if (!File.exists(img)) exit("File not found: " + img);

run("Bio-Formats Importer", "open=[" + img + "] color_mode=Composite view=Hyperstack stack_order=XYCZT");
if (nImages == 0) exit("Bio-Formats could not open: " + img);

getDimensions(w, h, nc, nz, nt);

// 0.5% 饱和裁剪，自动给每个通道一个合适的显示区间（只改显示，不改像素）
run("Enhance Contrast", "saturated=0.5 process_all");

// 每通道的显示参数面板
run("Channels Tool...");

// 4096 的图按 25% 显示，小图按 100%
z = 100;
if (w > 3000) z = 25;
if (w > 1500 && w <= 3000) z = 50;
run("Set...", "zoom=" + z);
