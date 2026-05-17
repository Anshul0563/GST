export const platforms = [
  { key: "amazon", name: "Amazon", files: "MTR_B2C CSV, B2B if available", color: "bg-[#FFF7ED] text-[#9A3412]" },
  { key: "flipkart", name: "Flipkart", files: "Sales report Excel, hidden sheets supported", color: "bg-[#EFF6FF] text-primary" },
  { key: "meesho", name: "Meesho", files: "tcs_sales, returns, tax invoice details", color: "bg-[#FDF2F8] text-[#BE185D]" },
  { key: "myntra", name: "Myntra", files: "Marketplace sales Excel", color: "bg-[#F5F3FF] text-[#6D28D9]" },
  { key: "jiomart", name: "JioMart", files: "Sales and settlement reports", color: "bg-[#ECFEFF] text-[#0E7490]" },
  { key: "snapdeal", name: "Snapdeal", files: "Order, invoice and return reports", color: "bg-[#F0FDF4] text-[#15803D]" },
  { key: "custom", name: "Custom Excel", files: "Normalized or mapped Excel/CSV", color: "bg-[#F8FAFC] text-slate-700" }
];

export const transactions = [
  { platform: "Meesho", invoice_no: "MSH-28491", order_id: "OD22901", invoice_date: "2026-04-04", buyer_state_code: "37", hsn: "711790", taxable_value: 1327.42, gst_rate: 3, igst: 39.82, cgst: 0, sgst: 0, tcs: 13.27, tds: 0, doc_type: "invoice", source_file: "tcs_sales.xlsx" },
  { platform: "Amazon", invoice_no: "IN-7781", order_id: "405-1122", invoice_date: "2026-04-08", buyer_state_code: "07", hsn: "7117", taxable_value: 2600, gst_rate: 3, igst: 0, cgst: 39, sgst: 39, tcs: 26, tds: 0, doc_type: "invoice", source_file: "MTR_B2C.csv" },
  { platform: "Flipkart", invoice_no: "FK-9982", order_id: "OD3301", invoice_date: "2026-04-12", buyer_state_code: "29", hsn: "4202", taxable_value: 4100, gst_rate: 18, igst: 738, cgst: 0, sgst: 0, tcs: 41, tds: 0, doc_type: "invoice", source_file: "sales-report.xlsx:hidden" },
  { platform: "Meesho", invoice_no: "CN-120", order_id: "OD22901", invoice_date: "2026-04-16", buyer_state_code: "37", hsn: "711790", taxable_value: -420, gst_rate: 3, igst: -12.6, cgst: 0, sgst: 0, tcs: -4.2, tds: 0, doc_type: "credit_note", source_file: "tcs_sales_return.xlsx" }
];

export const b2cs = [
  { sply_ty: "INTER", rt: 3, typ: "OE", pos: "37", txval: 907.42, iamt: 27.22, camt: 0, samt: 0, csamt: 0 },
  { sply_ty: "INTRA", rt: 3, typ: "OE", pos: "07", txval: 2600, iamt: 0, camt: 39, samt: 39, csamt: 0 },
  { sply_ty: "INTER", rt: 18, typ: "OE", pos: "29", txval: 4100, iamt: 738, camt: 0, samt: 0, csamt: 0 }
];

