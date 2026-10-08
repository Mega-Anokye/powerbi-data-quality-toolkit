// Deliveries: load, hide duplicate rows, and map typed customer names to the official customer list.
// Order of trust: 1) confirmed aliases  2) exact name  3) core-word match  4) fuzzy match (0.82)  5) keep the typed name.
let
    LoadCsv = (file) => Table.PromoteHeaders(Csv.Document(File.Contents(DataFolder & file), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]), [PromoteAllScalars = true]),
    Source = LoadCsv("deliveries.csv"),
    Blanks = Table.ReplaceValue(Source, "", null, Replacer.ReplaceValue, Table.ColumnNames(Source)),
    Typed = Table.TransformColumnTypes(Blanks, {{"DeliveryID", type text}, {"OrderID", type text}, {"CustomerNameTyped", type text}}),
    WithRow = Table.AddIndexColumn(Typed, "RowID", 1, 1, Int64.Type),
    // the same delivery on the same order entered twice: keep the first, hide the rest (the source is not changed)
    Deduped = Table.Distinct(Table.Buffer(WithRow), {"OrderID", "DeliveryID"}),

    Words = (t) => List.Select(Text.SplitAny(Text.Upper(Text.Trim(t)), " .,-'&/()#(tab)#(00A0)"), each _ <> ""),
    NameKey = (t) => if t = null then null else Text.Combine(Words(t), " "),
    Generic = {"LIMITED", "LTD", "ENTERPRISE", "ENTERPRISES", "ENT", "COMPANY", "CO", "AND", "THE", "SONS"},
    CoreKey = (t) => if t = null then null else let w = List.Select(Words(t), each not List.Contains(Generic, _)) in if List.IsEmpty(w) then NameKey(t) else Text.Combine(w, " "),

    Customers = Table.Buffer(Table.AddColumn(Table.AddColumn(LoadCsv("customers.csv"), "Key", each NameKey([OfficialName]), type text), "Core", each CoreKey([OfficialName]), type text)),
    Aliases = LoadCsv("customer_aliases.csv"),
    AliasKeyed = Table.Buffer(Table.Distinct(Table.AddColumn(Aliases, "Key", each NameKey([NameAsTyped]), type text), {"Key"})),
    Overrides = Table.Buffer(Table.SelectRows(Table.RenameColumns(Table.SelectColumns(Aliases, {"CustomerCode", "CityOverride"}), {{"CustomerCode", "OvCode"}}), each [CityOverride] <> null and [CityOverride] <> "")),
    ByKey = Table.Buffer(Table.Distinct(Customers, {"Key"})),
    ByCore = Table.Buffer(Table.Distinct(Customers, {"Core"})),

    // resolve each distinct typed name once
    TypedNames = Table.Buffer(Table.Distinct(Table.SelectRows(Table.AddColumn(Table.AddColumn(Table.SelectColumns(Deduped, {"CustomerNameTyped"}), "Key", each NameKey([CustomerNameTyped]), type text), "Core", each CoreKey([CustomerNameTyped]), type text), each [Key] <> null and [Key] <> ""), {"Key"})),
    A1 = Table.ExpandTableColumn(Table.NestedJoin(TypedNames, {"Key"}, AliasKeyed, {"Key"}, "A", JoinKind.LeftOuter), "A", {"CustomerCode"}, {"AliasCode"}),
    A2 = Table.ExpandTableColumn(Table.NestedJoin(A1, {"Key"}, ByKey, {"Key"}, "E", JoinKind.LeftOuter), "E", {"CustomerCode"}, {"ExactCode"}),
    A3 = Table.ExpandTableColumn(Table.NestedJoin(A2, {"Core"}, ByCore, {"Core"}, "C", JoinKind.LeftOuter), "C", {"CustomerCode"}, {"CoreCode"}),
    A4 = Table.ExpandTableColumn(Table.FuzzyNestedJoin(A3, {"Core"}, ByCore, {"Core"}, "F", JoinKind.LeftOuter, [IgnoreCase = true, IgnoreSpace = true, Threshold = 0.82, NumberOfMatches = 1]), "F", {"CustomerCode"}, {"FuzzyCode"}),
    Resolved = Table.AddColumn(Table.AddColumn(A4, "CustomerCode", each List.First(List.RemoveNulls({[AliasCode], [ExactCode], [CoreCode], [FuzzyCode]})), type text),
        "CustomerMatch", each if [AliasCode] <> null then "Confirmed (aliases)" else if [ExactCode] <> null or [CoreCode] <> null then "Exact (customer list)" else if [FuzzyCode] <> null then "Auto - fuzzy (review)" else "Unmatched (review)", type text),
    WithCust = Table.ExpandTableColumn(Table.NestedJoin(Resolved, {"CustomerCode"}, Customers, {"CustomerCode"}, "M", JoinKind.LeftOuter), "M", {"OfficialName", "City", "Region"}, {"OfficialName", "MasterCity", "Region"}),
    WithOv = Table.ExpandTableColumn(Table.NestedJoin(WithCust, {"CustomerCode"}, Overrides, {"OvCode"}, "O", JoinKind.LeftOuter), "O", {"CityOverride"}, {"CityOverride"}),
    Lookup = Table.Buffer(Table.AddColumn(WithOv, "City", each if [CityOverride] <> null then [CityOverride] else [MasterCity], type text)),

    Keyed = Table.AddColumn(Deduped, "Key", each NameKey([CustomerNameTyped]), type text),
    Merged = Table.ExpandTableColumn(Table.NestedJoin(Keyed, {"Key"}, Lookup, {"Key"}, "L", JoinKind.LeftOuter), "L", {"CustomerCode", "OfficialName", "City", "Region", "CustomerMatch"}),
    Customer = Table.AddColumn(Merged, "Customer", each if [OfficialName] <> null then [OfficialName] else [CustomerNameTyped], type text),
    Filled = Table.ReplaceValue(Customer, null, "Unmatched (review)", Replacer.ReplaceValue, {"CustomerMatch"}),
    Result = Table.TransformColumnTypes(Table.RemoveColumns(Filled, {"Key", "OfficialName"}), {{"CustomerCode", type text}, {"City", type text}, {"Region", type text}, {"CustomerMatch", type text}})
in
    Result
