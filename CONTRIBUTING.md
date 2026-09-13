# 贡献指南

感谢您愿意参与儒释道经典的整理！请在动手前先读完本指南。

## 一、内容原则

1. **公版原文优先**：仅整理已**进入公版领域**的原文（佛经、道经、十三经、注疏等）。
   - ✅ 可收录：大正藏 / 道藏 / 十三经注疏 / 四书章句集注 / 朱熹注 等古代整理本
   - ❌ 不可收录：当代学者独占版权的注释、译注、整理本（如「中华经典名著全本全注全译」系列等）
2. **忠实于底本**：保留异体字、避讳字、原文断句；如需加注请使用脚注或文末注释。
3. **不收录现代白话翻译**。

## 二、文件规范

1. **编码**：UTF-8（无 BOM）。
2. **文件名**：`中文.md`，使用全角字符。
3. **标题层级**：
   - `# 书名`（一级标题）
   - `## 卷/品`（二级）
   - `### 章/节`（三级）
   - 其余递减。
4. **YAML front-matter**：每个 `.md` 文件首部应包含：

   ```yaml
   ---
   title: "书名"
   dynasty: "朝代"
   author: "作者/译者/编者"
   category: "子分类（如：佛经·般若、道家·内丹）"
   source: "底本（公版来源说明）"
   public_domain: true
   ---
   ```

   模板参见 [`.github/metadata/books.yml`](.github/metadata/books.yml)。

5. **标点**：建议使用全角中文标点（，。：；？！），但要保持与底本一致。
   - 古代佛经原文多用「。」或「、」，保留即可。
   - 现代排版可统一为「，。：；？！」。
6. **段落**：段间空一行。

## 三、目录结构

```
佛家经典/
  经/         ← 佛经原文
  论/         ← 禅宗语录、祖师论著
儒家经典/       ← 四书五经、心学、蒙学
道家经典/       ← 原典、内丹、上清、全真
```

新文件请放入对应目录。如该目录下已无合适子目录，可直接放在顶级目录（如 `儒家经典/`）。

## 四、提交流程

```powershell
# 1. 拉取最新代码
git pull --rebase origin master

# 2. 修改或新增文件
#    （新文件请同步在 .github/metadata/books.yml 添加元数据）

# 3. 添加并提交
git add .
git commit -m "feat(<分类>): 简述改动"

# 4. 推送（同时同步 GitHub 与 Gitee）
git push origin master
```

### Commit 规范

参考 Conventional Commits：

- `feat:` 新增/补全一部经典
- `fix:` 修复错字、漏段、格式
- `docs:` 仅文档（README、CONTRIBUTING）
- `refactor:` 结构调整（如拆分大文件）
- `chore:` CI、脚本、.gitignore 等维护性改动

示例：

```
feat(佛家经典): 补全《八大人觉经》第五觉知
fix(道家经典): 修复《道德经》第三章标点
docs: 更新 CONTRIBUTING 贡献指南
```

## 五、脚本工具

- `scripts/add_frontmatter.py` — 根据 `.github/metadata/books.yml` 批量给文件添加 front-matter
- `scripts/gen_toc.py` — 重新生成 `00-总目录.md`

运行：

```powershell
py scripts/add_frontmatter.py
py scripts/gen_toc.py
```

新增经典后，请运行 `gen_toc.py` 刷新目录。

## 六、CI 校验

PR 将自动触发 GitHub Actions 检查：

- ✅ UTF-8 编码校验（无 BOM）
- ✅ front-matter 完整性校验
- ✅ 文件名规范校验
- ✅ Markdown 大致格式校验

如有失败，请按提示修复。

## 七、提问与讨论

如对内容选择、文本校对、整理规范有疑问，欢迎[提交 Issue](https://github.com/sxmwhl/confucianism-buddhism-taoism/issues) 讨论。
