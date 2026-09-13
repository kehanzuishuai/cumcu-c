function generate_paper_figures()
% Generate paper figures strictly from frozen C-problem outputs.

scriptDir = fileparts(mfilename('fullpath'));
projectDir = fullfile(fileparts(fileparts(scriptDir)), 'work', ...
    '审题codex_reference', '审题codex');
outDir = scriptDir;

apply_style();

summary = struct();
summary.generated_at = char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss'));
summary.project_dir = projectDir;
summary.output_dir = outDir;
summary.figures = strings(0, 1);

%% Figure 6.3: Q1 dispatch operation
q1 = readtable(fullfile(projectDir, 'results', 'q1_detail.csv'));
h = ((1:height(q1)) - 0.5) / 6;
fig = new_figure(6.8, 7.2);
axPos1 = [0.105 0.720 0.865 0.230];
axPos2 = [0.105 0.390 0.865 0.230];
axPos3 = [0.105 0.060 0.865 0.230];

ax = axes(fig, 'Position', axPos1);
pLoad = plot(ax, h, q1.load_kwh, '-', 'Color', color('primary'), 'LineWidth', 1.55, 'DisplayName', '负荷'); hold(ax, 'on');
pPV = plot(ax, h, q1.pv_kwh, '-', 'Color', color('improved'), 'LineWidth', 1.35, 'DisplayName', '光伏');
pPurchase = plot(ax, h, q1.normal_purchase_kwh, '-', 'Color', color('comparison'), 'LineWidth', 1.35, 'DisplayName', '外购电');
ylabel(ax, '单时段电量 / kWh');
lgd = legend(ax, [pLoad pPV pPurchase], 'Orientation', 'horizontal');
place_legend(lgd, 0.665); ax.Position = axPos1;
style_axis(ax, 'y'); figure_panel_label(fig, '(a)', axPos1);

ax = axes(fig, 'Position', axPos2);
pCharge = area(ax, h, q1.charge_bus_kwh, 'FaceColor', color('improved'), 'FaceAlpha', 0.55, ...
    'EdgeColor', 'none', 'DisplayName', '充电'); hold(ax, 'on');
pDischarge = area(ax, h, -q1.discharge_bus_kwh, 'FaceColor', color('comparison'), 'FaceAlpha', 0.62, ...
    'EdgeColor', 'none', 'DisplayName', '放电');
yline(ax, 0, '--', 'Color', color('baseline'), 'LineWidth', 1.0, 'HandleVisibility', 'off');
ylabel(ax, '储能流量 / kWh');
lgd = legend(ax, [pCharge pDischarge], 'Orientation', 'horizontal');
place_legend(lgd, 0.335); ax.Position = axPos2;
style_axis(ax, 'y'); figure_panel_label(fig, '(b)', axPos2);

ax = axes(fig, 'Position', axPos3);
stairs(ax, [0 h + 1/12], [q1.soc_open_kwh(1); q1.soc_close_kwh], ...
    'Color', color('primary'), 'LineWidth', 1.65);
yline(ax, 1200, '--', 'Color', color('baseline'), 'LineWidth', 1.0);
yline(ax, 10800, '--', 'Color', color('baseline'), 'LineWidth', 1.0);
xlabel(ax, '时刻 / h'); ylabel(ax, '储电量 / kWh');
style_axis(ax, 'both'); figure_panel_label(fig, '(c)', axPos3);
format_time_axes(findall(fig, 'Type', 'axes'));
export_figure(fig, outDir, 'fig_6_3_q1_dispatch');
summary.figures(end+1) = "fig_6_3_q1_dispatch";

%% Figure 6.4: no-storage baseline versus storage optimization
q1s = jsondecode(fileread(fullfile(projectDir, 'results', 'q1_summary.json')));
baseline = [q1s.baseline_no_storage_pv_first.cost_yuan, ...
    q1s.baseline_no_storage_pv_first.purchase_kwh, ...
    q1s.baseline_no_storage_pv_first.pv_spill_kwh];
optimized = [q1s.optimized.cost_yuan, q1s.optimized.purchase_kwh, ...
    q1s.optimized.pv_spill_or_surplus_kwh];
deltaPct = 100 * (optimized - baseline) ./ baseline;
relativeLevel = 100 * [baseline; optimized]' ./ baseline';
fig = new_figure(6.4, 3.8); ax = axes(fig); hold(ax, 'on');
b = bar(ax, 1:3, relativeLevel, 0.68, 'grouped', 'EdgeColor', 'none');
b(1).FaceColor = color('background'); b(1).DisplayName = '无储能基准';
b(2).FaceColor = color('improved'); b(2).DisplayName = '储能优化方案';
set(ax, 'XTick', 1:3, 'XTickLabel', {'总购电费用', '外购电量', '弃光量'});
ylabel(ax, '相对无储能基准 / %'); ylim(ax, [0 121]);
legend(ax, 'Location', 'northoutside', 'Orientation', 'horizontal');
drawnow;
baselineLabels = {sprintf('%.2f万元', baseline(1)/1e4), ...
    sprintf('%.2f万kWh', baseline(2)/1e4), sprintf('%.2f万kWh', baseline(3)/1e4)};
optimizedLabels = {sprintf('%.2f万元', optimized(1)/1e4), ...
    sprintf('%.2f万kWh', optimized(2)/1e4), sprintf('%.2f万kWh', optimized(3)/1e4)};
optimizedLabels{3} = '0';
for i = 1:3
    text(ax, b(1).XEndPoints(i), relativeLevel(i,1)+2.0, baselineLabels{i}, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', 'FontSize', 7.7);
    text(ax, b(2).XEndPoints(i), max(relativeLevel(i,2)+2.0, 2.0), optimizedLabels{i}, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', 'FontSize', 7.7);
    text(ax, i, 116.0, sprintf('%+.1f%%', deltaPct(i)), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'FontName', 'Times New Roman', 'FontSize', 8.3, 'FontWeight', 'bold');
end
style_axis(ax, 'y');
export_figure(fig, outDir, 'fig_6_4_q1_relative_improvement');
summary.figures(end+1) = "fig_6_4_q1_relative_improvement";

%% Figure 7.1-7.2: representative Q2 day and 80% quantile correction
q2 = readtable(fullfile(projectDir, 'results', 'q2_detail.csv'));
q2.date = string(q2.date);
dates = unique(q2.date, 'stable');
features = zeros(numel(dates), 3);
for i = 1:numel(dates)
    rows = q2.date == dates(i);
    actualNet = q2.actual_load_kw(rows) - q2.actual_pv_kw(rows);
    pointNet = q2.forecast_point_net_kw(rows);
    features(i, :) = [mean(abs(actualNet-pointNet)), mean(q2.risk_uplift_kw(rows)), mean(actualNet)];
end
q2Date = select_typical(dates, features);
rows = q2.date == q2Date;
actualNet = q2.actual_load_kw(rows) - q2.actual_pv_kw(rows);
pointNet = q2.forecast_point_net_kw(rows);
riskNet = pointNet + q2.risk_uplift_kw(rows);
residual = actualNet - pointNet;
h = ((1:sum(rows)) - 0.5) / 6;

fig = new_figure(6.8, 5.1);
tl = tiledlayout(fig, 2, 1, 'TileSpacing', 'compact', 'Padding', 'compact');
ax = nexttile(tl);
plot(ax, h, actualNet, '-', 'Color', color('primary'), 'LineWidth', 1.55, 'DisplayName', '实际净负载'); hold(ax, 'on');
plot(ax, h, pointNet, '--', 'Color', color('comparison'), 'LineWidth', 1.25, 'DisplayName', '基础净负载预测');
plot(ax, h, riskNet, '-', 'Color', color('improved'), 'LineWidth', 1.35, 'DisplayName', '80%分位数修正');
ylabel(ax, '净负载功率 / kW');
legend(ax, 'Location', 'northoutside', 'Orientation', 'horizontal');
style_axis(ax, 'both'); panel_label(ax, '(a)');

ax = nexttile(tl);
positive = max(residual, 0); negative = min(residual, 0);
area(ax, h, positive, 'FaceColor', color('risk'), 'FaceAlpha', 0.35, 'EdgeColor', 'none', 'DisplayName', '基础预测低估'); hold(ax, 'on');
area(ax, h, negative, 'FaceColor', color('uncertainty'), 'FaceAlpha', 0.85, 'EdgeColor', 'none', 'DisplayName', '基础预测高估');
plot(ax, h, q2.risk_uplift_kw(rows), '-', 'Color', color('improved'), 'LineWidth', 1.35, 'DisplayName', '80%分位安全裕量');
yline(ax, 0, '--', 'Color', color('baseline'), 'LineWidth', 1.0, 'HandleVisibility', 'off');
xlabel(ax, '时刻 / h'); ylabel(ax, '功率偏差 / kW');
legend(ax, 'Location', 'northoutside', 'Orientation', 'horizontal');
style_axis(ax, 'both'); panel_label(ax, '(b)');
format_time_axes(findall(fig, 'Type', 'axes'));
export_figure(fig, outDir, 'fig_7_1_2_q2_typical_day_q80');
summary.figures(end+1) = "fig_7_1_2_q2_typical_day_q80";

%% Figure 7.4: Raincloud of daily emergency-purchase cost
q2a = readtable(fullfile(projectDir, 'results', 'q2_component_ablation_daily.csv'));
a0 = q2a.emergency_cost_yuan(string(q2a.strategy) == "A0_base_point");
q80 = q2a.emergency_cost_yuan(string(q2a.strategy) == "A1_fixed_q80");
zA0 = log10(1 + a0); zQ80 = log10(1 + q80);
fig = new_figure(6.4, 3.7); ax = axes(fig); hold(ax, 'on');
raincloud_horizontal(ax, zA0, 2, color('comparison'));
raincloud_horizontal(ax, zQ80, 1, color('primary'));
set(ax, 'YTick', [1 2], 'YTickLabel', {'80%分位数修正', '不作风险修正'}, 'YLim', [0.34 2.55]);
ticksCost = [0 100 1000 10000 100000];
set(ax, 'XTick', log10(1+ticksCost), 'XTickLabel', {'0','100','1千','1万','10万'});
xlabel(ax, '每日紧急购电费用 / 元（log_{10}(1+x)刻度）');
style_axis(ax, 'x');
export_figure(fig, outDir, 'fig_7_4_q2_emergency_raincloud');
summary.figures(end+1) = "fig_7_4_q2_emergency_raincloud";

%% Figure 7.4: Q2 risk-quantile cost-risk trade-off
q2tau = readtable(fullfile(projectDir, 'experiments', 'paper_supplemental_20260912', ...
    'q2_risk_quantile_sensitivity', 'results.csv'));
fig = new_figure(6.8, 3.3);
tl = tiledlayout(fig, 1, 2, 'TileSpacing', 'compact', 'Padding', 'compact');
ax1 = nexttile(tl);
tradeoff_path(ax1, q2tau.emergency_purchase_kwh/1e4, q2tau.total_purchase_cost_yuan/1e6, q2tau.tau, true);
xlabel(ax1, '紧急购电量 / 万kWh（对数坐标）'); ylabel(ax1, '总购电费用 / 百万元');
style_axis(ax1, 'both'); panel_label(ax1, '(a)');
ax2 = nexttile(tl);
zoom = q2tau.tau >= 0.6;
tradeoff_path(ax2, q2tau.emergency_purchase_kwh(zoom)/1e4, q2tau.total_purchase_cost_yuan(zoom)/1e6, q2tau.tau(zoom), false);
xlabel(ax2, '紧急购电量 / 万kWh');
style_axis(ax2, 'both'); panel_label(ax2, '(b)');
export_figure(fig, outDir, 'fig_7_4_q2_quantile_tradeoff');
summary.figures(end+1) = "fig_7_4_q2_quantile_tradeoff";

%% Figure 8.3: Q3 plan matrices
q3d = readtable(fullfile(projectDir, 'results', 'q3_daily.csv'));
q3d.date = string(q3d.date);
q3Features = [q3d.upward_adjustment_kwh + q3d.downward_adjustment_kwh, ...
    q3d.emergency_purchase_kwh, q3d.total_cost_yuan];
q3Date = select_typical(q3d.date, q3Features);
q3v = readtable(fullfile(projectDir, 'results', 'q3_plan_versions.csv'));
q3v.date = string(q3v.date); q3v.issue_time = string(q3v.issue_time);
issue = ["00:00","06:00","12:00","18:00"];
plan = nan(4, 144); change = nan(4, 144);
for i = 1:4
    r = q3v.date == q3Date & q3v.issue_time == issue(i) & q3v.target_slot >= 1 & q3v.target_slot <= 144;
    slots = q3v.target_slot(r);
    plan(i, slots) = q3v.new_effective_plan_kwh(r);
    change(i, slots) = q3v.new_effective_plan_kwh(r) - q3v.original_plan_kwh(r);
end
fig = new_figure(6.8, 4.8); tl = tiledlayout(fig, 2, 1, 'TileSpacing', 'compact', 'Padding', 'compact');
ax = nexttile(tl); matrix_image(ax, plan, sequential_map(256), [0 max(plan,[],'all','omitnan')]);
set(ax, 'YTick', 1:4, 'YTickLabel', cellstr(issue), 'XTick', 1:24:144, 'XTickLabel', {'0','4','8','12','16','20'});
ylabel(ax, '计划发布时间'); cb=colorbar(ax); cb.Label.String='计划购电量 / kWh'; panel_label(ax, '(a)');
ax = nexttile(tl); lim = max(abs(change), [], 'all', 'omitnan'); matrix_image(ax, change, diverging_map(257), [-lim lim]);
set(ax, 'YTick', 1:4, 'YTickLabel', cellstr(issue), 'XTick', 1:24:144, 'XTickLabel', {'0','4','8','12','16','20'});
xlabel(ax, '交付时刻 / h'); ylabel(ax, '计划发布时间'); cb=colorbar(ax); cb.Label.String='相对0:00初始计划的调整量 / kWh'; panel_label(ax, '(b)');
export_figure(fig, outDir, 'fig_8_3_q3_plan_heatmaps');
summary.figures(end+1) = "fig_8_3_q3_plan_heatmaps";

%% Figure 8.3: update combinations and Shapley contributions
upd = readtable(fullfile(projectDir, 'experiments', 'paper_supplemental_20260912', ...
    'q3_update_combinations_alpha05', 'results.csv'));
comb = upd(string(upd.record_type)=="combination", :);
shp = upd(string(upd.record_type)=="shapley", :);
fig = new_figure(6.8, 3.2); tl = tiledlayout(fig, 1, 3, 'TileSpacing', 'compact', 'Padding', 'compact');
maxSaving = max(comb.cost_saving_vs_no_update_yuan)/1e4;
for state18 = 0:1
    mat = nan(2,2);
    for i = 1:height(comb)
        if comb.update_18(i)==state18
            mat(comb.update_12(i)+1, comb.update_06(i)+1) = comb.cost_saving_vs_no_update_yuan(i)/1e4;
        end
    end
    ax=nexttile(tl); imagesc(ax, mat, [0 maxSaving]); colormap(ax, sequential_map(256)); axis(ax,'image');
    set(ax,'XTick',1:2,'XTickLabel',{'否','是'},'YTick',1:2,'YTickLabel',{'否','是'},'YDir','normal');
    xlabel(ax,'06:00是否更新'); ylabel(ax,'12:00是否更新');
    for rr=1:2, for cc=1:2, text(ax,cc,rr,sprintf('%.1f',mat(rr,cc)),'HorizontalAlignment','center','FontSize',8.0); end, end
    title(ax, sprintf('18:00%s', ternary(state18==1,'更新','不更新')), 'FontSize',9,'FontWeight','normal');
    panel_label(ax, sprintf('(%c)', 'a'+state18));
end
ax=nexttile(tl); vals=shp.shapley_cost_saving_yuan/1e4; y=1:height(shp);
for i=1:height(shp), line(ax,[0 vals(i)],[y(i) y(i)],'Color',color('background'),'LineWidth',1.2); hold(ax,'on'); end
scatter(ax, vals, y, 42, color('primary'), 'filled');
set(ax,'YTick',y,'YTickLabel',{'06:00','12:00','18:00'},'YDir','reverse'); xlabel(ax,'平均边际费用节省 / 万元');
for i=1:numel(vals), text(ax,vals(i),y(i),sprintf(' %.1f',vals(i)),'VerticalAlignment','middle','FontSize',7.8); end
xlim(ax,[0 max(vals)*1.2]);
ylim(ax,[0.7 3.3]);
style_axis(ax,'x'); panel_label(ax,'(c)');
cb=colorbar(nexttile_handle(fig,1)); cb.Label.String='费用节省 / 万元';
export_figure(fig, outDir, 'fig_8_3_q3_update_combinations');
summary.figures(end+1) = "fig_8_3_q3_update_combinations";

%% Figure 8.4: information-module bubble matrix
info = readtable(fullfile(projectDir, 'experiments', 'paper_supplemental_20260912', ...
    'q3_information_modules_alpha05', 'results.csv'));
info = info(string(info.record_type)=="combination", :);
fig = new_figure(6.8, 4.05);
cmax = max(info.cost_saving_vs_all_off_yuan)/1e4;
smax = max(info.emergency_reduction_vs_all_off_kwh);
bubbleAxes = gobjects(2,1);
for fb=0:1
    ax=axes(fig,'Position',[0.15+0.43*fb 0.34 0.30 0.56]); bubbleAxes(fb+1)=ax; hold(ax,'on');
    for i=1:height(info)
        if info.load_feedback_alpha05(i)==fb
            x=info.new_pv_release(i)+1; y=info.state_update(i)+1;
            s=55 + 520*max(info.emergency_reduction_vs_all_off_kwh(i),0)/max(smax,eps);
            scatter(ax,x,y,s,info.cost_saving_vs_all_off_yuan(i)/1e4,'filled','MarkerEdgeColor',[0.35 0.35 0.35],'LineWidth',0.45);
            text(ax,x,y,sprintf('%.1f',info.cost_saving_vs_all_off_yuan(i)/1e4), ...
                'HorizontalAlignment','center','VerticalAlignment','middle','FontSize',7.5);
        end
    end
    set(ax,'XLim',[0.5 2.5],'YLim',[0.5 2.5],'XTick',1:2,'XTickLabel',{'新光伏预报：关','新光伏预报：开'}, ...
        'YTick',1:2,'YTickLabel',{'实际储电量更新：关','实际储电量更新：开'},'FontSize',8.0); axis(ax,'square'); box(ax,'on'); grid(ax,'off');
    colormap(ax,sequential_map(256)); clim(ax,[0 cmax]); title(ax,ternary(fb==1,'使用负载反馈','不使用负载反馈'),'FontSize',9,'FontWeight','normal');
    panel_label(ax,sprintf('(%c)','a'+fb));
end
ax=axes(fig,'Position',[0.12 0.02 0.76 0.21]); axis(ax,[0 1 0 1]); axis(ax,'off'); hold(ax,'on');
legendVals=[0 50000 100000]; xPos=[0.18 0.5 0.82];
for i=1:3
    s=55+520*legendVals(i)/max(smax,eps); scatter(ax,xPos(i),0.52,s,[0.75 0.82 0.9],'filled','MarkerEdgeColor',[0.35 0.35 0.35]);
    text(ax,xPos(i),0.13,sprintf('%g',legendVals(i)),'HorizontalAlignment','center','FontSize',8.0);
end
text(ax,0.5,0.91,'圆面积：紧急购电减少量 / kWh','HorizontalAlignment','center','FontSize',8.1);
text(ax,0.5,0.02,'圆内数字与颜色：费用节省 / 万元','HorizontalAlignment','center','FontSize',8.1);
cb=colorbar(bubbleAxes(2),'Location','eastoutside'); cb.Label.String='费用节省 / 万元';
cb.Position=[0.91 0.39 0.022 0.46];
export_figure(fig, outDir, 'fig_8_4_q3_information_bubble_matrix');
summary.figures(end+1) = "fig_8_4_q3_information_bubble_matrix";

%% Figure 8.4: alpha cost-risk phase path
alp = readtable(fullfile(projectDir, 'experiments', 'q3_alpha_five_point_sensitivity', 'results', 'results.csv'));
fig = new_figure(6.2, 3.7); ax=axes(fig); hold(ax,'on');
alphaRiskX=alp.emergency_purchase_kwh/1e4;
plot(ax, alphaRiskX, alp.total_purchase_cost_yuan/1e6, '-', 'Color', color('background'), 'LineWidth', 1.25);
scatter(ax, alphaRiskX, alp.total_purchase_cost_yuan/1e6, 34, color('primary'), 'filled');
sel = abs(alp.alpha-0.5)<1e-12;
scatter(ax, alphaRiskX(sel), alp.total_purchase_cost_yuan(sel)/1e6, 78, color('improved'), 'filled', 'MarkerEdgeColor',[0.25 0.25 0.25]);
alphaLabels = {'α=0','α=0.25','α=0.50','α=0.75','α=1.00'};
for i=1:height(alp)
    text(ax,alphaRiskX(i),alp.total_purchase_cost_yuan(i)/1e6,['  ' alphaLabels{i}], ...
        'FontSize',8.0,'VerticalAlignment',ternary(i<=3,'bottom','top'));
end
xlabel(ax,'全年紧急购电量 / 万kWh'); ylabel(ax,'全年总购电费用 / 百万元');
style_axis(ax,'both');
export_figure(fig, outDir, 'fig_8_4_q3_alpha_tradeoff');
summary.figures(end+1) = "fig_8_4_q3_alpha_tradeoff";

%% Figure 9.1: predicted versus actual price hexbin
q42 = readtable(fullfile(projectDir, 'results', 'q4_2_detail.csv'));
x=q42.forecast_price_yuan_per_kwh; y=q42.actual_price_yuan_per_kwh;
fig = new_figure(5.3, 4.4); ax=axes(fig); hold(ax,'on');
hexbin_plot(ax,x,y,38);
limit=max([x;y])*1.03; plot(ax,[0 limit],[0 limit],'--','Color',color('baseline'),'LineWidth',1.1);
xlim(ax,[0 limit]); ylim(ax,[0 limit]); axis(ax,'square');
xlabel(ax,'预测电价 / (元·kWh^{-1})'); ylabel(ax,'实际电价 / (元·kWh^{-1})');
mae=mean(abs(x-y)); rmse=sqrt(mean((x-y).^2));
text(ax,0.04,0.94,sprintf('样本数 = %d\n平均绝对误差 = %.4f\n均方根误差 = %.4f',numel(x),mae,rmse), ...
    'Units','normalized','VerticalAlignment','top','FontSize',8.2,'BackgroundColor','w','Margin',3);
style_axis(ax,false);
export_figure(fig, outDir, 'fig_9_1_q4_price_hexbin');
summary.figures(end+1) = "fig_9_1_q4_price_hexbin";

%% Figure 9.2-9.3: representative Q4-3 operating day
q43 = readtable(fullfile(projectDir, 'results', 'q4_3_detail.csv'));
q43.date=string(q43.date); q43Dates=unique(q43.date,'stable'); q43Features=zeros(numel(q43Dates),3);
for i=1:numel(q43Dates)
    r=q43.date==q43Dates(i);
    q43Features(i,:)=[max(q43.actual_price_yuan_per_kwh(r))-min(q43.actual_price_yuan_per_kwh(r)), ...
        sum(q43.total_cost_yuan(r)), sum(q43.charge_bus_kwh(r)+q43.discharge_bus_kwh(r))];
end
q4Date=select_typical(q43Dates,q43Features); r=q43.date==q4Date; h=((1:sum(r))-0.5)/6;
fig=new_figure(6.8,6.4); tl=tiledlayout(fig,3,1,'TileSpacing','compact','Padding','compact');
ax=nexttile(tl); plot(ax,h,q43.actual_price_yuan_per_kwh(r),'-','Color',color('primary'),'LineWidth',1.55,'DisplayName','实际电价'); hold(ax,'on');
plot(ax,h,q43.forecast_price_yuan_per_kwh(r),'--','Color',color('comparison'),'LineWidth',1.25,'DisplayName','预测电价');
ylabel(ax,'电价 / (元·kWh^{-1})'); ylim(ax,[0.3 1.55]); legend(ax,'Location','northwest','Orientation','horizontal'); style_axis(ax,'both'); panel_label(ax,'(a)');
ax=nexttile(tl); plot(ax,h,q43.effective_purchase_kwh(r),'-','Color',color('primary'),'LineWidth',1.35,'DisplayName','实际执行购电量'); hold(ax,'on');
area(ax,h,q43.charge_bus_kwh(r),'FaceColor',color('improved'),'FaceAlpha',0.42,'EdgeColor','none','DisplayName','充电');
area(ax,h,-q43.discharge_bus_kwh(r),'FaceColor',color('comparison'),'FaceAlpha',0.52,'EdgeColor','none','DisplayName','放电');
yline(ax,0,'--','Color',color('baseline'),'HandleVisibility','off'); ylabel(ax,'电量 / kWh'); legend(ax,'Location','northoutside','Orientation','horizontal'); style_axis(ax,'both'); panel_label(ax,'(b)');
ax=nexttile(tl); stairs(ax,[0 h+1/12],[q43.soc_open_kwh(find(r,1));q43.soc_close_kwh(r)],'Color',color('primary'),'LineWidth',1.6);
yline(ax,1200,'--','Color',color('baseline')); yline(ax,10800,'--','Color',color('baseline'));
xlabel(ax,'时刻 / h'); ylabel(ax,'储电量 / kWh'); style_axis(ax,'both'); panel_label(ax,'(c)');
format_time_axes(findall(fig,'Type','axes'));
export_figure(fig,outDir,'fig_9_2_3_q4_dispatch');
summary.figures(end+1) = "fig_9_2_3_q4_dispatch";

%% Figure 9.4: grouped comparison of fixed repricing and reoptimization
q4s=jsondecode(fileread(fullfile(projectDir,'results','q4_summary.json')));
fixed=[q4s.fixed_strategy_repricing.q2_fixed_decisions.total_cost_yuan; q4s.fixed_strategy_repricing.q3_fixed_decisions.total_cost_yuan]/1e6;
reopt=[q4s.q4_2.main.total_cost_yuan; q4s.q4_3.strategies.q4_3_all_main.total_cost_yuan]/1e6;
fig=new_figure(6.4,3.8); ax=axes(fig); hold(ax,'on');
costBars=bar(ax,1:2,[fixed reopt],0.66,'grouped','EdgeColor','none');
costBars(1).FaceColor=color('comparison'); costBars(1).DisplayName='原策略按实际电价重计';
costBars(2).FaceColor=color('primary'); costBars(2).DisplayName='按预测电价重新优化';
set(ax,'XTick',1:2,'XTickLabel',{'仅在0:00制定计划','允许日内调整'});
ylabel(ax,'全年总购电费用 / 百万元'); ylim(ax,[0 16.2]);
legend(ax,'Location','northoutside','Orientation','horizontal'); drawnow;
for i=1:2
    text(ax,costBars(1).XEndPoints(i),fixed(i)-0.45,sprintf('%.2f',fixed(i)), ...
        'HorizontalAlignment','center','VerticalAlignment','top','FontSize',7.8);
    text(ax,costBars(2).XEndPoints(i),reopt(i)-0.45,sprintf('%.2f',reopt(i)), ...
        'HorizontalAlignment','center','VerticalAlignment','top','FontSize',7.8,'Color','w');
    capY=max(fixed(i),reopt(i))+0.35;
    plot(ax,[costBars(1).XEndPoints(i) costBars(2).XEndPoints(i)],[capY capY],'-','Color',color('baseline'),'LineWidth',0.8,'HandleVisibility','off');
    text(ax,i,capY+0.20,sprintf('节省 %.2f 万元',(fixed(i)-reopt(i))*100), ...
        'HorizontalAlignment','center','VerticalAlignment','bottom','FontSize',8.1);
end
style_axis(ax,'y');
export_figure(fig,outDir,'fig_9_4_q4_reprice_dumbbell');
summary.figures(end+1) = "fig_9_4_q4_reprice_dumbbell";

summary.selected_dates = struct('q2_typical_day',char(q2Date),'q3_typical_day',char(q3Date),'q4_typical_day',char(q4Date));
summary.selection_rule = 'Minimum robust standardized distance to the multivariate yearly median; no visual cherry-picking.';
write_json(fullfile(outDir,'build_summary.json'),summary);
make_contact_sheet(outDir, summary.figures);
disp(jsonencode(summary, 'PrettyPrint', true));
end

function apply_style()
set(groot,'defaultFigureColor','w');
set(groot,'defaultAxesFontName','SimSun','defaultTextFontName','SimSun');
set(groot,'defaultAxesFontSize',8.5,'defaultTextFontSize',8.5);
set(groot,'defaultAxesLineWidth',0.8,'defaultLineLineWidth',1.4);
set(groot,'defaultAxesTickDir','out','defaultAxesBox','off');
set(groot,'defaultLegendBox','off','defaultLegendFontSize',8.2);
set(groot,'defaultTextInterpreter','tex','defaultLegendInterpreter','none','defaultAxesTickLabelInterpreter','none');
end

function fig = new_figure(w,h)
fig=figure('Units','inches','Position',[0.5 0.5 w h],'Color','w','Visible','off');
end

function c=color(role)
switch role
    case 'primary', c=[15 77 146]/255;
    case 'secondary', c=[55 117 186]/255;
    case 'comparison', c=[227 160 106]/255;
    case 'improved', c=[127 174 121]/255;
    case 'risk', c=[182 67 66]/255;
    case 'baseline', c=[118 118 118]/255;
    case 'background', c=[207 206 206]/255;
    case 'uncertainty', c=[220 232 243]/255;
    otherwise, c=[0 0 0];
end
end

function style_axis(ax,gridMode)
ax.FontName='SimSun'; ax.FontSize=8.5; ax.LineWidth=0.8; ax.TickDir='out';
ax.XColor=[0.22 0.22 0.22]; ax.YColor=[0.22 0.22 0.22];
ax.Layer='top'; ax.Box='off';
if islogical(gridMode) && ~gridMode, grid(ax,'off'); return; end
grid(ax,'on'); ax.GridColor=[0.85 0.85 0.85]; ax.GridAlpha=0.45; ax.MinorGridAlpha=0;
if strcmp(gridMode,'x'), ax.YGrid='off'; end
if strcmp(gridMode,'y'), ax.XGrid='off'; end
end

function panel_label(ax,label)
text(ax,0.01,0.97,label,'Units','normalized','FontName','Times New Roman','FontSize',9, ...
    'FontWeight','bold','VerticalAlignment','top','HorizontalAlignment','left');
end

function place_legend(lgd,y)
drawnow;
lgd.Units='normalized'; p=lgd.Position;
p(1)=0.5-p(3)/2; p(2)=y;
lgd.Position=p; lgd.Location='none';
end

function figure_panel_label(fig,label,axPosition)
annotation(fig,'textbox',[axPosition(1), axPosition(2)+axPosition(4)+0.006, 0.05, 0.025], ...
    'String',label,'LineStyle','none','Margin',0,'FitBoxToText','off', ...
    'FontName','Times New Roman','FontSize',9,'FontWeight','bold', ...
    'HorizontalAlignment','left','VerticalAlignment','bottom');
end

function format_time_axes(axesList)
for ax=reshape(axesList,1,[])
    if isa(ax,'matlab.graphics.axis.Axes')
        xlim(ax,[0 24]); set(ax,'XTick',0:4:24);
    end
end
end

function export_figure(fig,outDir,id)
pdfPath=fullfile(outDir,[id '.pdf']); pngPath=fullfile(outDir,[id '.png']);
exportgraphics(fig,pdfPath,'ContentType','vector','BackgroundColor','white');
exportgraphics(fig,pngPath,'Resolution',400,'BackgroundColor','white');
make_a4_preview(pngPath,fullfile(outDir,'previews',[id '_a4.png']));
close(fig);
end

function make_a4_preview(imagePath,outPath)
if ~exist(fileparts(outPath),'dir'), mkdir(fileparts(outPath)); end
img=imread(imagePath); [ih,iw,~]=size(img);
pageW=round(8.27*180); pageH=round(11.69*180); targetW=round(6.5*180);
targetH=round(targetW*ih/iw);
if targetH>round(10.2*180), targetH=round(10.2*180); targetW=round(targetH*iw/ih); end
scaled=imresize(img,[targetH targetW]);
if size(scaled,3)==1, scaled=repmat(scaled,1,1,3); end
canvas=uint8(255*ones(pageH,pageW,3));
x0=floor((pageW-targetW)/2)+1; y0=floor((pageH-targetH)/2)+1;
canvas(y0:y0+targetH-1,x0:x0+targetW-1,:)=scaled(:,:,1:3);
imwrite(canvas,outPath);
end

function date=select_typical(dates,features)
z=zeros(size(features));
for j=1:size(features,2)
    med=median(features(:,j),'omitnan'); scale=median(abs(features(:,j)-med),'omitnan');
    if scale<eps, scale=std(features(:,j),'omitnan'); end
    if scale<eps, scale=1; end
    z(:,j)=(features(:,j)-med)/scale;
end
[~,idx]=min(sum(z.^2,2,'omitnan')); date=dates(idx);
end

function raincloud_horizontal(ax,z,y,c)
gridX=linspace(min(z)-0.12,max(z)+0.12,260); density=local_kde(z,gridX);
density=0.34*density/max(density);
patch(ax,[gridX fliplr(gridX)],[y+density y+zeros(size(density))],c,'FaceAlpha',0.34,'EdgeColor',c,'LineWidth',0.8);
n=numel(z); sequence=(1:n)';
jitter=0.150*sin(sequence*2.399963229728653)+0.050*cos(sequence*0.754877666246693);
scatter(ax,z,y-0.38+jitter,3.5,c,'filled','MarkerFaceAlpha',0.14,'MarkerEdgeAlpha',0.03);
q=[local_quantile(z,.05),local_quantile(z,.25),local_quantile(z,.5),local_quantile(z,.75),local_quantile(z,.95)];
plot(ax,[q(1) q(5)],[y-0.12 y-0.12],'-','Color',[0.35 0.35 0.35],'LineWidth',1.0);
rectangle(ax,'Position',[q(2),y-0.19,q(4)-q(2),0.14],'FaceColor',[1 1 1],'EdgeColor',c,'LineWidth',1.0);
plot(ax,[q(3) q(3)],[y-0.19 y-0.05],'-','Color',[0.2 0.2 0.2],'LineWidth',1.2);
plot(ax,q(5),y-0.12,'d','Color',color('risk'),'MarkerFaceColor','w','MarkerSize',4.5);
end

function d=local_kde(x,g)
x=x(isfinite(x)); n=numel(x); s=std(x);
bw=1.06*s*n^(-1/5); if ~isfinite(bw)||bw<0.035, bw=0.035; end
d=zeros(size(g));
for i=1:n, d=d+exp(-0.5*((g-x(i))/bw).^2); end
d=d/(n*bw*sqrt(2*pi));
end

function q=local_quantile(x,p)
x=sort(x(isfinite(x))); pos=1+(numel(x)-1)*p; lo=floor(pos); hi=ceil(pos);
if lo==hi, q=x(lo); else, q=x(lo)+(pos-lo)*(x(hi)-x(lo)); end
end

function tradeoff_path(ax,x,y,tau,useLog)
hold(ax,'on'); plot(ax,x,y,'-','Color',color('background'),'LineWidth',1.2);
scatter(ax,x,y,34,color('primary'),'filled'); sel=abs(tau-.8)<1e-12;
scatter(ax,x(sel),y(sel),76,color('improved'),'filled','MarkerEdgeColor',[0.25 .25 .25]);
for i=1:numel(tau), text(ax,x(i),y(i),sprintf('  τ=%.2g',tau(i)),'FontSize',7.8,'VerticalAlignment','bottom'); end
if useLog, set(ax,'XScale','log'); end
end

function matrix_image(ax,m,cmap,limits)
im=imagesc(ax,m,limits); im.AlphaData=isfinite(m); ax.Color=[0.91 0.91 0.91];
colormap(ax,cmap); box(ax,'on'); ax.LineWidth=0.8; ax.FontName='SimSun'; ax.FontSize=8.5;
end

function m=sequential_map(n)
t=linspace(0,1,n)'; c0=[.96 .98 1]; c1=color('primary'); m=(1-t).*c0+t.*c1;
end

function m=diverging_map(n)
n1=ceil(n/2); n2=n-n1+1; blue=[.23 .46 .72]; white=[.98 .98 .98]; red=[.72 .26 .26];
t1=linspace(0,1,n1)'; t2=linspace(0,1,n2)'; m1=(1-t1).*blue+t1.*white; m2=(1-t2).*white+t2.*red; m=[m1;m2(2:end,:)];
end

function out=ternary(cond,a,b)
if cond, out=a; else, out=b; end
end

function ax=nexttile_handle(fig,index)
axs=findall(fig,'Type','axes'); axs=flipud(axs); ax=axs(min(index,numel(axs)));
end

function hexbin_plot(ax,x,y,nx)
x=x(:); y=y(:); xmin=min(x); xmax=max(x); ymin=min(y); ymax=max(y);
radius=(xmax-xmin)/(1.5*nx); q=(2/3)*(x-xmin)/radius;
r=(-1/3*(x-xmin)+sqrt(3)/3*(y-ymin))/radius;
[qi,ri]=axial_round(q,r);
[pairs,~,idx]=unique([qi ri],'rows'); counts=accumarray(idx,1);
cx=xmin+radius*(3/2*pairs(:,1)); cy=ymin+radius*sqrt(3)*(pairs(:,2)+pairs(:,1)/2);
keep=cx>=xmin-radius & cx<=xmax+radius & cy>=ymin-radius & cy<=ymax+radius;
cx=cx(keep); cy=cy(keep); counts=counts(keep); angles=(0:5)*pi/3;
vals=log10(1+counts); cmap=sequential_map(256); colormap(ax,cmap); clim(ax,[min(vals) max(vals)]);
for i=1:numel(cx)
    patch(ax,cx(i)+radius*cos(angles),cy(i)+radius*sin(angles),vals(i), ...
        'EdgeColor','none','FaceColor','flat');
end
cb=colorbar(ax); tickCounts=unique(round(logspace(0,log10(max(counts)),4)));
cb.Ticks=log10(1+tickCounts); cb.TickLabels=string(tickCounts); cb.Label.String='样本数 / 个';
end

function [qi,ri]=axial_round(q,r)
x=q; z=r; y=-x-z; rx=round(x); ry=round(y); rz=round(z);
dx=abs(rx-x); dy=abs(ry-y); dz=abs(rz-z);
mask=dx>dy & dx>dz; rx(mask)=-ry(mask)-rz(mask);
mask2=~mask & dy>dz; ry(mask2)=-rx(mask2)-rz(mask2); %#ok<NASGU>
mask3=~mask & ~mask2; rz(mask3)=-rx(mask3)-ry(mask3);
qi=rx; ri=rz;
end

function write_json(path,payload)
fid=fopen(path,'w','n','UTF-8'); assert(fid>0,'Cannot open JSON output');
cleanup=onCleanup(@()fclose(fid)); fwrite(fid,jsonencode(payload,'PrettyPrint',true),'char');
end

function make_contact_sheet(outDir,ids)
paths=strings(numel(ids),1); for i=1:numel(ids), paths(i)=fullfile(outDir,ids(i)+".png"); end
fig=figure('Units','inches','Position',[0 0 13.5 16],'Color','w','Visible','off');
tl=tiledlayout(fig,4,3,'TileSpacing','compact','Padding','compact');
for i=1:numel(paths)
    ax=nexttile(tl); img=imread(paths(i)); image(ax,img); axis(ax,'image'); axis(ax,'off');
    title(ax,strrep(ids(i),'_','\_'),'Interpreter','none','FontSize',7.2,'FontWeight','normal');
end
exportgraphics(fig,fullfile(outDir,'contact_sheet.png'),'Resolution',180,'BackgroundColor','white'); close(fig);
end
