function generate_fig_8_4_q3_information_bars()
% Regenerate only Figure 8-4 from the frozen information-combination results.

scriptDir = fileparts(mfilename('fullpath'));
projectDir = fullfile(fileparts(fileparts(scriptDir)), 'work', ...
    '审题codex_reference', '审题codex');
dataPath = fullfile(projectDir, 'experiments', 'paper_supplemental_20260912', ...
    'q3_information_modules_alpha05', 'results.csv');
data = readtable(dataPath);
comb = data(string(data.record_type) == "combination", :);

costValues = comb.cost_saving_vs_all_off_yuan / 1e4;
emergencyValues = comb.emergency_reduction_vs_all_off_kwh / 1e4;
combLabels = { ...
    '三类信息均不使用', ...
    '仅更新实际储电量', ...
    '仅使用新光伏预报', ...
    '仅使用负载反馈', ...
    '实际储电量更新 + 新光伏预报', ...
    '实际储电量更新 + 负载反馈', ...
    '新光伏预报 + 负载反馈', ...
    '三类信息均使用'};

apply_style();
fig = figure('Units','inches','Position',[0.5 0.5 7.2 4.5], ...
    'Color','w','Visible','off');

ax1 = axes(fig, 'Position', [0.31 0.13 0.29 0.78]);
barh(ax1, 1:8, costValues, 0.58, 'FaceColor', [15 77 146]/255, ...
    'EdgeColor', 'none');
set(ax1, 'YTick', 1:8, 'YTickLabel', combLabels, 'YDir', 'reverse');
xlabel(ax1, '费用节省 / 万元');
xlim(ax1, [0 max(costValues)*1.19]); ylim(ax1, [0.4 8.6]);
style_axis(ax1); panel_label(ax1, '(a)');
add_bar_labels(ax1, costValues, 1:8, 1, max(costValues));

ax2 = axes(fig, 'Position', [0.69 0.13 0.28 0.78]);
barh(ax2, 1:8, emergencyValues, 0.58, 'FaceColor', [127 174 121]/255, ...
    'EdgeColor', 'none');
set(ax2, 'YTick', 1:8, 'YTickLabel', repmat({''},1,8), 'YDir', 'reverse');
xlabel(ax2, '紧急购电减少量 / 万kWh');
xlim(ax2, [0 max(emergencyValues)*1.19]); ylim(ax2, [0.4 8.6]);
style_axis(ax2); panel_label(ax2, '(b)');
add_bar_labels(ax2, emergencyValues, 1:8, 2, max(emergencyValues));

export_target(fig, scriptDir, 'fig_8_4_q3_information_bubble_matrix');
end

function add_bar_labels(ax, values, y, decimals, xmax)
for i = 1:numel(values)
    tx = values(i) + 0.018*xmax;
    if values(i) == 0, tx = 0.018*xmax; end
    text(ax, tx, y(i), sprintf(['%.' num2str(decimals) 'f'], values(i)), ...
        'HorizontalAlignment', 'left', 'VerticalAlignment', 'middle', ...
        'FontName', 'Times New Roman', 'FontSize', 8.0);
end
end

function apply_style()
set(groot, 'defaultFigureColor', 'w');
set(groot, 'defaultAxesFontName', 'SimSun', 'defaultTextFontName', 'SimSun');
set(groot, 'defaultAxesFontSize', 8.5, 'defaultTextFontSize', 8.5);
set(groot, 'defaultAxesLineWidth', 0.8, 'defaultAxesTickDir', 'out');
set(groot, 'defaultAxesBox', 'off', 'defaultTextInterpreter', 'tex');
set(groot, 'defaultAxesTickLabelInterpreter', 'none');
end

function style_axis(ax)
ax.FontName = 'SimSun'; ax.FontSize = 8.5; ax.LineWidth = 0.8;
ax.TickDir = 'out'; ax.Box = 'off'; ax.Layer = 'top';
ax.XColor = [0.22 0.22 0.22]; ax.YColor = [0.22 0.22 0.22];
grid(ax, 'on'); ax.XGrid = 'on'; ax.YGrid = 'off';
ax.GridColor = [0.85 0.85 0.85]; ax.GridAlpha = 0.45;
end

function panel_label(ax, label)
text(ax, 0.01, 0.98, label, 'Units', 'normalized', ...
    'FontName', 'Times New Roman', 'FontSize', 9, 'FontWeight', 'bold', ...
    'VerticalAlignment', 'top', 'HorizontalAlignment', 'left');
end

function export_target(fig, outDir, id)
pdfPath = fullfile(outDir, [id '.pdf']);
pngPath = fullfile(outDir, [id '.png']);
exportgraphics(fig, pdfPath, 'ContentType', 'vector', 'BackgroundColor', 'white');
exportgraphics(fig, pngPath, 'Resolution', 400, 'BackgroundColor', 'white');
make_a4_preview(pngPath, fullfile(outDir, 'previews', [id '_a4.png']));
close(fig);
end

function make_a4_preview(imagePath, outPath)
if ~exist(fileparts(outPath), 'dir'), mkdir(fileparts(outPath)); end
img = imread(imagePath); [ih, iw, ~] = size(img);
pageW = round(8.27*180); pageH = round(11.69*180); targetW = round(6.5*180);
targetH = round(targetW*ih/iw);
scaled = imresize(img, [targetH targetW]);
if size(scaled,3) == 1, scaled = repmat(scaled,1,1,3); end
canvas = uint8(255*ones(pageH,pageW,3));
x0 = floor((pageW-targetW)/2)+1; y0 = floor((pageH-targetH)/2)+1;
canvas(y0:y0+targetH-1,x0:x0+targetW-1,:) = scaled(:,:,1:3);
imwrite(canvas, outPath);
end
