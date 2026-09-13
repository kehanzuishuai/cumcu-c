function generate_fig_7_4_q2_quantile_tradeoff()
% Regenerate only Figure 7-4 (right): risk-quantile cost-risk trade-off.

scriptDir = fileparts(mfilename('fullpath'));
projectDir = fullfile(fileparts(fileparts(scriptDir)), 'work', ...
    '审题codex_reference', '审题codex');

apply_style();
q2tau = readtable(fullfile(projectDir, 'experiments', ...
    'paper_supplemental_20260912', 'q2_risk_quantile_sensitivity', 'results.csv'));

fig = figure('Units','inches','Position',[0.5 0.5 6.8 3.3], ...
    'Color','w','Visible','off');
tl = tiledlayout(fig, 1, 2, 'TileSpacing', 'compact', 'Padding', 'compact');

ax1 = nexttile(tl);
draw_tradeoff(ax1, q2tau.emergency_purchase_kwh/1e4, ...
    q2tau.total_purchase_cost_yuan/1e6, q2tau.tau, true);
xlabel(ax1, '紧急购电量 / 万kWh（对数坐标）');
ylabel(ax1, '总购电费用 / 百万元');
style_axis(ax1); panel_label(ax1, '(a)');

ax2 = nexttile(tl);
zoom = q2tau.tau >= 0.6;
draw_tradeoff(ax2, q2tau.emergency_purchase_kwh(zoom)/1e4, ...
    q2tau.total_purchase_cost_yuan(zoom)/1e6, q2tau.tau(zoom), false);
xlabel(ax2, '紧急购电量 / 万kWh');
style_axis(ax2); panel_label(ax2, '(b)');

id = 'fig_7_4_q2_quantile_tradeoff';
pdfPath = fullfile(scriptDir, [id '.pdf']);
pngPath = fullfile(scriptDir, [id '.png']);
exportgraphics(fig, pdfPath, 'ContentType', 'vector', 'BackgroundColor', 'white');
exportgraphics(fig, pngPath, 'Resolution', 400, 'BackgroundColor', 'white');
make_a4_preview(pngPath, fullfile(scriptDir, 'previews', [id '_a4.png']));
close(fig);
end

function draw_tradeoff(ax, x, y, tau, useLog)
hold(ax, 'on');
plot(ax, x, y, '-', 'Color', [207 206 206]/255, 'LineWidth', 1.2);
scatter(ax, x, y, 34, [15 77 146]/255, 'filled');
selected = abs(tau-0.8) < 1e-12;
scatter(ax, x(selected), y(selected), 76, [127 174 121]/255, 'filled', ...
    'MarkerEdgeColor', [0.25 0.25 0.25]);

if useLog
    set(ax, 'XScale', 'log');
    directions = {'left','right','below','above','below','above'};
else
    directions = {'left','right','above','right','above'};
end

drawnow;
for i = 1:numel(tau)
    place_point_label(ax, x(i), y(i), sprintf('τ=%.2g', tau(i)), directions{i});
end
end

function place_point_label(ax, x, y, label, direction)
% Use fixed axes-relative gaps so label distances remain visually uniform.
xl = ax.XLim; yl = ax.YLim;
if strcmp(ax.XScale, 'log')
    xn = (log10(x)-log10(xl(1))) / (log10(xl(2))-log10(xl(1)));
else
    xn = (x-xl(1)) / (xl(2)-xl(1));
end
yn = (y-yl(1)) / (yl(2)-yl(1));
gapX = 0.022; gapY = 0.035;
switch direction
    case 'left'
        xn = xn-gapX; ha = 'right'; va = 'middle';
    case 'right'
        xn = xn+gapX; ha = 'left'; va = 'middle';
    case 'above'
        yn = yn+gapY; ha = 'center'; va = 'bottom';
    otherwise
        yn = yn-gapY; ha = 'center'; va = 'top';
end
text(ax, xn, yn, label, 'Units', 'normalized', 'FontSize', 7.8, ...
    'HorizontalAlignment', ha, 'VerticalAlignment', va, 'Clipping', 'off');
end

function apply_style()
set(groot, 'defaultFigureColor', 'w');
set(groot, 'defaultAxesFontName', 'SimSun', 'defaultTextFontName', 'SimSun');
set(groot, 'defaultAxesFontSize', 8.5, 'defaultTextFontSize', 8.5);
set(groot, 'defaultAxesLineWidth', 0.8, 'defaultLineLineWidth', 1.4);
set(groot, 'defaultAxesTickDir', 'out', 'defaultAxesBox', 'off');
set(groot, 'defaultTextInterpreter', 'tex', 'defaultAxesTickLabelInterpreter', 'none');
end

function style_axis(ax)
ax.FontName = 'SimSun'; ax.FontSize = 8.5; ax.LineWidth = 0.8;
ax.TickDir = 'out'; ax.XColor = [0.22 0.22 0.22];
ax.YColor = [0.22 0.22 0.22]; ax.Layer = 'top'; ax.Box = 'off';
grid(ax, 'on'); ax.GridColor = [0.85 0.85 0.85];
ax.GridAlpha = 0.45; ax.MinorGridAlpha = 0;
end

function panel_label(ax, label)
text(ax, 0.01, 0.97, label, 'Units', 'normalized', ...
    'FontName', 'Times New Roman', 'FontSize', 9, 'FontWeight', 'bold', ...
    'VerticalAlignment', 'top', 'HorizontalAlignment', 'left');
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
