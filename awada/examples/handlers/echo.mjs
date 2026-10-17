// Command handlers receive a redacted context on stdin and return a standard reply.
let input = "";
for await (const chunk of process.stdin) input += chunk;
const context = JSON.parse(input);
process.stdout.write(JSON.stringify({ text: context.args || "请输入需要回显的内容。" }));
