from pydantic import BaseModel


class NotionConfig(BaseModel):
    number_list_stack: int = 1


class MarkdownConverter:
    @classmethod
    def convert_blocks(cls, blocks):
        # Assumes we have a list of blocks passed into this function
        assert isinstance(blocks, list)
        converted_blocks = [cls.convert_block(block) for block in blocks]

        final_blocks = []
        config = NotionConfig()
        for block in converted_blocks:
            block, config = cls.postprocess_block(block, config)
            final_blocks.append(block)

        return "\n".join(final_blocks)

    @classmethod
    def postprocess_block(cls, block, config: NotionConfig):
        if block.startswith("(-n-)"):
            block = block.replace("(-n-)", f"{config.number_list_stack}. ")
            config.number_list_stack += 1
        else:
            config.number_list_stack = 1

        return block, config

    @classmethod
    def convert_block(cls, block):
        try:
            block_type = block["type"]
        except Exception as e:
            import pdb

            pdb.set_trace()
            print(e)

        if block_type == "paragraph":
            return cls.convert_paragraph(block)
        elif block_type.startswith("heading_"):
            return cls.convert_heading(block)
        elif block_type == "bulleted_list_item":
            return cls.convert_bullet_list(block)
        elif block_type == "text":
            return cls.convert_text(block)
        elif block_type == "divider":
            return "-" * 50
        elif block_type == "numbered_list_item":
            return cls.convert_numbered_list(block)
        elif block_type == "quote":
            return cls.convert_quote(block)
        elif block_type == "table":
            return cls.convert_table(block)
        elif block_type == "table_row":
            return cls.convert_table_row(block)
        elif block_type == "code":
            return cls.convert_code(block)
        elif block_type == "mention":
            return cls.convert_mention(block)
        elif block_type == "child_page":
            return cls.convert_child_page(block)
        else:
            raise ValueError(f"Unsupported block type: {block_type}")

    @classmethod
    def convert_child_page(cls, child_page_block):
        assert child_page_block["type"] == "child_page"
        formatted_link = (
            f"https://www.notion.so/{child_page_block['id'].replace('-','')}"
        )
        return f"[{child_page_block['child_page']['title']}]({formatted_link})"

    @classmethod
    def convert_mention(cls, mention_block):
        assert mention_block["type"] == "mention"

        mention_type = mention_block["mention"]["type"]

        if mention_type == "user":
            user = mention_block["mention"]["user"]
            return f"[{mention_block['plain_text']}](mailto:{user['person']['email']})"
        elif mention_type == "date":
            return f"[{mention_block['plain_text']}]({mention_block['mention']['date']['start']})"
        elif mention_type == "page":
            return f"[{mention_block['plain_text']}]({mention_block['href']})"
        else:
            raise ValueError(f"Unsupported mention type: {mention_type}")

    @classmethod
    def convert_code(cls, code_block):
        assert code_block["type"] == "code"
        children = code_block["code"]["rich_text"]
        language = code_block["code"]["language"]

        return (
            f"```{language}\n"
            + "".join(cls.convert_block(child) for child in children)
            + "\n```"
        )

    @classmethod
    def convert_table_row(cls, table_row_block):
        assert table_row_block["type"] == "table_row"
        children = []

        for child_items in table_row_block["table_row"]["cells"]:
            child_content = [cls.convert_block(child) for child in child_items]
            children.append("".join(child_content))

        return cls.format_table_row(children)

    @classmethod
    def format_table_row(cls, row):
        return "| " + " | ".join(row) + " |"

    @classmethod
    def convert_table(cls, table_block):
        assert table_block["type"] == "table"
        children = table_block["children"]

        if len(children) == 0:
            return ""

        children = [cls.convert_block(child) for child in children]

        num_columns = table_block["table"]["table_width"]
        children.insert(
            1,
            cls.format_table_row(["---" for _ in range(num_columns)]),
        )

        return "\n".join(children)

    @classmethod
    def convert_quote(cls, quote_block):
        assert quote_block["type"] == "quote"
        children = quote_block["quote"]["rich_text"]

        return "> " + "".join(cls.convert_block(child) for child in children)

    @classmethod
    def convert_paragraph(cls, paragraph_block):
        assert paragraph_block["type"] == "paragraph"

        children = paragraph_block["paragraph"]["rich_text"]

        if not children:
            return ""

        return "".join(cls.convert_block(child) for child in children) + "\n"

    @classmethod
    def convert_numbered_list(cls, numbered_list_block):
        assert numbered_list_block["type"] == "numbered_list_item"
        children = numbered_list_block["numbered_list_item"]["rich_text"]

        for child in children:
            if child["type"] != "text":
                raise ValueError(f"Unsupported child type: {child['type']}")

        list_text = [cls.convert_block(child) for child in children]
        nested_lists = (
            [cls.convert_block(child) for child in numbered_list_block["children"]]
            if "children" in numbered_list_block
            else []
        )

        nested_offset = "\n    "

        result = "(-n-) " + nested_offset.join(
            item.strip() for item in nested_offset.join(list_text).splitlines()
        )
        # Format nested lists with appropriate offsets
        if nested_lists:
            if "-n-" not in nested_lists[0]:
                nested_lists_formatted = nested_offset.join(
                    [nested_offset.join(item.splitlines()) for item in nested_lists]
                )
                result += nested_offset + nested_lists_formatted
            else:
                nested_lists_formatted = "".join(
                    [nested_offset.join(item.splitlines()) for item in nested_lists]
                )
                items = [
                    f"(-n-){item}"
                    for item in nested_lists_formatted.split("(-n-)")
                    if item.strip()
                ]
                config = NotionConfig()

                processed_nested_lists = ""
                for item in items:
                    processed_item, config = cls.postprocess_block(item, config)
                    processed_nested_lists += nested_offset + processed_item

                result += processed_nested_lists.rstrip()

        return result

    @classmethod
    def convert_text(cls, text_block):
        text = text_block["text"]["content"]
        annotations = text_block["annotations"]

        if annotations["code"]:
            return f"`{text}`"

        if annotations["bold"]:
            text = f"**{text}**"

        if annotations["italic"]:
            text = f"*{text}*"

        if annotations["strikethrough"]:
            text = f"~~{text}~~"

        if text_block["text"]["link"]:
            text = f"[{text}]({text_block['text']['link']['url']})"

        return text

    @classmethod
    def convert_heading(cls, heading_block):
        assert heading_block["type"].startswith("heading_")

        heading_type = heading_block["type"]

        text = heading_block[heading_type]["rich_text"][0]["text"]["content"]

        return f"\n{'#' * int(heading_type[len('heading_'):])} {text}\n"

    @classmethod
    def convert_bullet_list(cls, list_block):
        assert list_block["type"] == "bulleted_list_item"
        children = list_block["bulleted_list_item"]["rich_text"]

        for child in children:
            if child["type"] != "text":
                raise ValueError(f"Unsupported child type: {child['type']}")

        return "- " + "".join([cls.convert_block(child) for child in children])
