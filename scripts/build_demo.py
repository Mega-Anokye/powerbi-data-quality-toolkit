"""Build the demo Power BI project (demo/) from the pattern files in power-query/ and dax/.

The demo is generated so that it always matches the patterns. Run from the repo root:
    python scripts/build_demo.py [path-to-sample-data-folder]
The optional path sets the DataFolder parameter (default: this repo's sample-data folder).
Open demo/Demo.pbip in Power BI Desktop afterwards and click Refresh.
"""
import json
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / 'demo'
data_folder = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'sample-data')
data_folder = data_folder.rstrip('\\/') + '\\'
gid = lambda: str(uuid.uuid5(uuid.NAMESPACE_URL, 'pbi-dq-toolkit/' + next(_seq)))  # stable ids between builds
_seq = (str(i) for i in range(100000))
hexid = lambda: uuid.uuid5(uuid.NAMESPACE_URL, 'pbi-dq-toolkit/v/' + next(_seq)).hex[:20]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def write_json(path, obj):
    write(path, json.dumps(obj, indent=2) + '\n')


def indent(code, tabs=4):
    return '\n'.join(('\t' * tabs + line) if line.strip() else '' for line in code.strip().splitlines())


def strip_comments(dax):
    return '\n'.join(l for l in dax.splitlines() if not l.lstrip().startswith('//'))


if DEMO.exists():
    shutil.rmtree(DEMO)

# ---------------- semantic model (TMDL) ----------------
SM = DEMO / 'Demo.SemanticModel'
D = SM / 'definition'
write_json(SM / '.platform', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json',
                              'metadata': {'type': 'SemanticModel', 'displayName': 'Demo'}, 'config': {'version': '2.0', 'logicalId': gid()}})
write_json(SM / 'definition.pbism', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json', 'version': '4.2', 'settings': {}})
write(D / 'database.tmdl', 'database\n\tcompatibilityLevel: 1606\n')
write(D / 'model.tmdl', '\n'.join([
    'model Model', '\tculture: en-US', '\tdefaultPowerBIDataSourceVersion: powerBI_V3', '\tsourceQueryCulture: en-GB', '\tdataAccessOptions',
    '\t\tlegacyRedirects', '\t\treturnErrorValuesAsNull', '', 'annotation PBI_QueryOrder = ["DataFolder","Orders","Deliveries"]', '',
    "ref table Orders", "ref table Deliveries", "ref table 'Data Checks'", "ref table _Measures", '']))
write(D / 'expressions.tmdl', '\n'.join([
    f'expression DataFolder = "{data_folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
    f'\tlineageTag: {gid()}', '', '\tannotation PBI_ResultType = Text', '']))


def table(name, cols, partition, description=None):
    q = (lambda n: f"'{n}'" if ' ' in n else n)
    out = ([f'/// {description}'] if description else []) + [f'table {q(name)}', f'\tlineageTag: {gid()}', '']
    for c, dt, extra in cols:
        out += [f'\tcolumn {q(c)}', f'\t\tdataType: {dt}'] + [f'\t\t{e}' for e in extra]
        out += [f'\t\tlineageTag: {gid()}', '\t\tsummarizeBy: none', f'\t\tsourceColumn: {partition[0] == "calculated" and "[" + c + "]" or c}', '',
                '\t\tannotation SummarizationSetBy = Automatic', '']
    kind, code = partition
    out += [f'\tpartition {q(name)} = {kind}', '\t\tmode: import', '\t\tsource =', indent(code), '']
    if kind == 'm':
        out += ['\tannotation PBI_ResultType = Table', '']
    write(D / 'tables' / f'{name}.tmdl', '\n'.join(out))


S, DT, N, I = 'string', 'dateTime', 'double', 'int64'
dt_fmt = ['formatString: dd mmm yyyy hh:mm']
num_fmt = ['formatString: #,0']
table('Orders', [
    ('OrderID', S, []), ('SubmittedDate', DT, dt_fmt), ('AssignedDate', DT, dt_fmt), ('ApprovedDate', DT, dt_fmt), ('Status', S, []),
    ('VendorNameTyped', S, []), ('VendorAccount', S, []), ('VehicleNumber', S, []), ('InvoiceAmount', N, num_fmt), ('InitialAmount', N, num_fmt),
    ('InitialRef', S, []), ('InitialPaidDate', DT, dt_fmt), ('FinalAmount', N, num_fmt), ('FinalRef', S, []), ('CompletedDate', DT, dt_fmt),
    ('RowID', I, ['formatString: 0']), ('Vendor', S, []), ('VendorMatch', S, []), ('EffectiveStatus', S, [])],
    ('m', (ROOT / 'power-query' / 'Orders.pq').read_text(encoding='utf-8')), 'One row per order. Vendor names standardised; 5-day rule in EffectiveStatus.')
table('Deliveries', [
    ('DeliveryID', S, []), ('OrderID', S, []), ('CustomerNameTyped', S, []), ('RowID', I, ['formatString: 0']), ('CustomerCode', S, []),
    ('City', S, []), ('Region', S, []), ('CustomerMatch', S, []), ('Customer', S, [])],
    ('m', (ROOT / 'power-query' / 'Deliveries.pq').read_text(encoding='utf-8')), 'One row per delivery. Customer names mapped to the official list.')
table('Data Checks', [
    ('Severity', S, ["sortByColumn: 'Severity Order'"]), ('Severity Order', I, ['isHidden', 'formatString: 0']), ('Check', S, []), ('Where', S, []),
    ('Order', S, []), ('Vendor', S, []), ('Field', S, []), ('Value Entered', S, []), ('Problem', S, []), ('What To Do', S, []),
    ('Amount Involved', N, num_fmt)],
    ('calculated', strip_comments((ROOT / 'dax' / 'data-checks-table.dax').read_text(encoding='utf-8'))),
    'Data-quality checks re-run on every refresh. One row per suspicious entry.')

# measures from dax/measures.dax  (lines "Name = expression")
measures = []
for line in (ROOT / 'dax' / 'measures.dax').read_text(encoding='utf-8').splitlines():
    if line.strip() and not line.lstrip().startswith('//') and ' = ' in line:
        name, expr = line.split(' = ', 1)
        fmt = None if name == 'Data Check Color' else ('#,0' if 'Issues' in name else '#,0')
        measures.append((name.strip(), expr.strip(), fmt))
mlines = ['table _Measures', f'\tlineageTag: {gid()}', '']
for name, expr, fmt in measures:
    mlines += [f"\tmeasure '{name}' = {expr}"] + ([f'\t\tformatString: {fmt}'] if fmt else []) + [f'\t\tlineageTag: {gid()}', '']
mlines += ['\tcolumn _', '\t\tisHidden', f'\t\tlineageTag: {gid()}', '\t\tisNameInferred', '\t\tsourceColumn: [_]', '',
           '\tpartition _Measures = calculated', '\t\tmode: import', '\t\tsource = ROW("_", BLANK())', '']
write(D / 'tables' / '_Measures.tmdl', '\n'.join(mlines))

# ---------------- report (PBIR) ----------------
RP = DEMO / 'Demo.Report'
write_json(RP / '.platform', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json',
                              'metadata': {'type': 'Report', 'displayName': 'Demo'}, 'config': {'version': '2.0', 'logicalId': gid()}})
write_json(RP / 'definition.pbir', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json',
                                    'version': '4.0', 'datasetReference': {'byPath': {'path': '../Demo.SemanticModel'}}})
RD = RP / 'definition'
write_json(RD / 'version.json', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json', 'version': '2.0.0'})
write_json(RD / 'report.json', {
    '$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json',
    'themeCollection': {'baseTheme': {'name': 'CY24SU10', 'reportVersionAtImport': {'visual': '1.8.95', 'report': '2.0.95', 'page': '1.3.95'}, 'type': 'SharedResources'}},
    'resourcePackages': [{'name': 'SharedResources', 'type': 'SharedResources', 'items': [{'name': 'CY24SU10', 'path': 'BaseThemes/CY24SU10.json', 'type': 'BaseTheme'}]}],
    'settings': {'useStylableVisualContainerHeader': True, 'exportDataMode': 'AllowSummarized', 'defaultDrillFilterOtherVisuals': True,
                 'allowChangeFilterTypes': True, 'useEnhancedTooltips': True, 'useDefaultAggregateDisplayName': True}})
shutil.copy(ROOT / 'scripts' / 'assets' / 'CY24SU10.json', (RP / 'StaticResources' / 'SharedResources' / 'BaseThemes').mkdir(parents=True, exist_ok=True) or RP / 'StaticResources' / 'SharedResources' / 'BaseThemes' / 'CY24SU10.json')

VC = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json'
lit = lambda v: {'expr': {'Literal': {'Value': v}}}
color = lambda c: {'solid': {'color': lit(f"'{c}'")}}


def container(title=None):
    v = {'background': [{'properties': {'show': lit('true'), 'color': color('#FFFFFF'), 'transparency': lit('0D')}}],
         'border': [{'properties': {'show': lit('true'), 'color': color('#DDE2EA'), 'radius': lit('6D')}}]}
    v['title'] = [{'properties': ({'show': lit('true'), 'text': lit(f"'{title}'"), 'fontSize': lit('11D'), 'bold': lit('true'), 'fontColor': color('#1F2933')}
                                  if title else {'show': lit('false')})}]
    return v


def col(field, display=None, entity='Data Checks'):
    p = {'field': {'Column': {'Expression': {'SourceRef': {'Entity': entity}}, 'Property': field}}, 'queryRef': f'{entity}.{field}', 'nativeQueryRef': field}
    if display:
        p['displayName'] = display
    return p


def meas(field, display):
    return {'field': {'Measure': {'Expression': {'SourceRef': {'Entity': '_Measures'}}, 'Property': field}}, 'queryRef': f'_Measures.{field}',
            'nativeQueryRef': field, 'displayName': display}


def visual(x, y, w, h, z, body):
    return {'$schema': VC, 'name': hexid(), 'position': {'x': x, 'y': y, 'z': z, 'height': h, 'width': w, 'tabOrder': z}, 'visual': body}


page_id = 'b1d2c3e4f5a6b7c8d9e0'
vis = [visual(0, 0, 1280, 48, 1000, {
    'visualType': 'textbox',
    'objects': {'general': [{'properties': {'paragraphs': [{'textRuns': [
        {'value': 'Data checks   ', 'textStyle': {'fontWeight': 'bold', 'fontSize': '18pt', 'color': '#FFFFFF'}},
        {'value': 'A total looks wrong? The entry causing it is listed here. Re-checked on every refresh.', 'textStyle': {'fontSize': '11pt', 'color': '#C9D6E6'}}]}]}}]},
    'visualContainerObjects': {'background': [{'properties': {'show': lit('true'), 'color': color('#1F3A5A'), 'transparency': lit('0D')}}], 'title': [{'properties': {'show': lit('false')}}]},
    'drillFilterOtherVisuals': True})]
cards = [('Total Paid', 'Total paid (confirmed)', '#1F3A5A'), ('High Data Issues', 'High - check now', '#C8423B'), ('Medium Data Issues', 'Medium', '#E0A100'),
         ('Low Data Issues', 'Low (typos)', '#6CA6E0'), ('Amount In High Issues', 'Amount in High entries', '#1F3A5A')]
for i, (m, label, c) in enumerate(cards):
    vis.append(visual(16 + i * 252, 56, 240, 84, 1100 + i * 10, {
        'visualType': 'card', 'query': {'queryState': {'Values': {'projections': [meas(m, label)]}}},
        'objects': {'labels': [{'properties': {'fontSize': lit('22D'), 'color': color(c)}}],
                    'categoryLabels': [{'properties': {'show': lit('true'), 'fontSize': lit('10D'), 'color': color('#52606D')}}]},
        'visualContainerObjects': container(), 'drillFilterOtherVisuals': True}))
for i, (field, label) in enumerate([('Severity', 'Severity'), ('Check', 'Check'), ('Vendor', 'Vendor')]):
    vis.append(visual(16 + i * 420, 152, 408, 56, 1200 + i * 10, {
        'visualType': 'slicer', 'query': {'queryState': {'Values': {'projections': [dict(col(field, label), active=True)]}}},
        'objects': {'data': [{'properties': {'mode': lit("'Dropdown'")}}], 'header': [{'properties': {'show': lit('true'), 'text': lit(f"'{label}'"), 'fontColor': color('#1F2933')}}]},
        'visualContainerObjects': container(), 'drillFilterOtherVisuals': True}))
tcols = [('Severity', None, 62), ('Check', None, 130), ('Where', None, 104), ('Order', None, 90), ('Vendor', None, 112), ('Field', None, 104),
         ('Value Entered', 'Value entered', 100), ('Problem', None, 290), ('What To Do', 'What to do', 140), ('Amount Involved', 'Amount', 78)]
vis.append(visual(16, 220, 1248, 484, 1300, {
    'visualType': 'tableEx',
    'query': {'queryState': {'Values': {'projections': [col(f, d) for f, d, _ in tcols]}},
              'sortDefinition': {'sort': [{'field': {'Column': {'Expression': {'SourceRef': {'Entity': 'Data Checks'}}, 'Property': 'Severity'}}, 'direction': 'Ascending'},
                                          {'field': {'Column': {'Expression': {'SourceRef': {'Entity': 'Data Checks'}}, 'Property': 'Amount Involved'}}, 'direction': 'Descending'}]}},
    'objects': {
        'columnHeaders': [{'properties': {'fontColor': color('#FFFFFF'), 'backColor': color('#1F3A5A'), 'bold': lit('true'), 'wordWrap': lit('true')}}],
        'grid': [{'properties': {'rowPadding': lit('4D'), 'gridHorizontalColor': color('#DDE2EA')}}],
        'values': [{'properties': {'fontColorPrimary': color('#1F2933'), 'backColorSecondary': color('#F7F9FC'), 'wordWrap': lit('true')}},
                   {'properties': {'backColor': {'solid': {'color': {'expr': {'Measure': {'Expression': {'SourceRef': {'Entity': '_Measures'}}, 'Property': 'Data Check Color'}}}}},
                                   'fontColor': color('#FFFFFF')},
                    'selector': {'data': [{'dataViewWildcard': {'matchingOption': 1}}], 'metadata': 'Data Checks.Severity'}}],
        'total': [{'properties': {'totals': lit('false')}}],
        'columnWidth': [{'properties': {'value': lit(f'{w}D')}, 'selector': {'metadata': f'Data Checks.{f}'}} for f, _, w in tcols]},
    'visualContainerObjects': container('Flagged entries - High first, biggest amount first'),
    'drillFilterOtherVisuals': True}))

PD = RD / 'pages' / page_id
write_json(PD / 'page.json', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json',
                              'name': page_id, 'displayName': 'Data checks', 'displayOption': 'FitToPage', 'height': 720, 'width': 1280,
                              'objects': {'background': [{'properties': {'color': color('#F4F6F9'), 'transparency': lit('0D')}}]}})
for v in vis:
    write_json(PD / 'visuals' / v['name'] / 'visual.json', v)
write_json(RD / 'pages' / 'pages.json', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json',
                                         'pageOrder': [page_id], 'activePageName': page_id})
write_json(DEMO / 'Demo.pbip', {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json',
                                'version': '1.0', 'artifacts': [{'report': {'path': 'Demo.Report'}}], 'settings': {'enableAutoRecovery': True}})
print(f'demo built in {DEMO} (DataFolder = {data_folder})')
