// Orders: load, clean, standardise vendor names and apply the 5-day completion rule.
// DataFolder is a text parameter pointing at the sample-data folder (ending in a backslash).
let
    Source = Csv.Document(File.Contents(DataFolder & "orders.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // empty cells arrive as "" - make them real nulls so numbers and dates type cleanly
    Blanks = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, Table.ColumnNames(Promoted)),
    Typed = Table.TransformColumnTypes(Blanks, {
        {"OrderID", type text}, {"SubmittedDate", type datetime}, {"AssignedDate", type datetime}, {"ApprovedDate", type datetime},
        {"Status", type text}, {"VendorNameTyped", type text}, {"VendorAccount", type text}, {"VehicleNumber", type text},
        {"InvoiceAmount", type number}, {"InitialAmount", type number}, {"InitialRef", type text}, {"InitialPaidDate", type datetime},
        {"FinalAmount", type number}, {"FinalRef", type text}, {"CompletedDate", type datetime}}, "en-GB"),
    Trimmed = Table.TransformColumns(Typed, {{"VendorNameTyped", each if _ = null then null else Text.Trim(_), type text},
        {"InitialRef", each if _ = null then null else Text.Trim(_), type text}, {"FinalRef", each if _ = null then null else Text.Trim(_), type text}}),
    WithRow = Table.AddIndexColumn(Trimmed, "RowID", 1, 1, Int64.Type),

    // ===== Vendor standardisation: exact alias match first, then fuzzy (threshold 0.85) =====
    Key = (t) => if t = null then null else Text.Upper(Text.Combine(List.Select(Text.SplitAny(t, " .,-'&/()"), each _ <> ""), " ")),
    Master = Table.Buffer(Table.AddColumn(Table.PromoteHeaders(Csv.Document(File.Contents(DataFolder & "vendors.csv"), [Delimiter = ",", Encoding = 65001])), "Key", each Key([NameAsTyped]), type text)),
    Keyed = Table.AddColumn(WithRow, "Key", each Key([VendorNameTyped]), type text),
    Exact = Table.ExpandTableColumn(Table.NestedJoin(Keyed, {"Key"}, Master, {"Key"}, "E", JoinKind.LeftOuter), "E", {"StandardVendor"}, {"ExactVendor"}),
    Fuzzy = Table.ExpandTableColumn(Table.FuzzyNestedJoin(Exact, {"Key"}, Master, {"Key"}, "F", JoinKind.LeftOuter,
        [IgnoreCase = true, IgnoreSpace = true, Threshold = 0.85, NumberOfMatches = 1]), "F", {"StandardVendor"}, {"FuzzyVendor"}),
    Vendor = Table.AddColumn(Fuzzy, "Vendor", each if [ExactVendor] <> null then [ExactVendor] else if [FuzzyVendor] <> null then [FuzzyVendor] else Text.Upper([VendorNameTyped]), type text),
    Match = Table.AddColumn(Vendor, "VendorMatch", each if [ExactVendor] <> null then "Confirmed (master)" else if [FuzzyVendor] <> null then "Auto - fuzzy (review)" else "Unmatched (review)", type text),

    // ===== 5-day rule: initial paid, no final requested after 5 days = completed on the initial payment =====
    Effective = Table.AddColumn(Match, "EffectiveStatus", each
        if [Status] = "Initial Payment Made" and [FinalAmount] = null and [InitialPaidDate] <> null
            and Duration.Days(DateTime.LocalNow() - [InitialPaidDate]) > 5
        then "Completed - initial only" else [Status], type text),
    Result = Table.RemoveColumns(Effective, {"Key", "ExactVendor", "FuzzyVendor"})
in
    Result
