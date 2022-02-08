import difflib

import disnake
import pandas as pd
from menus.menu import Menu

import discordbot.config_discordbot as cfg
from discordbot.config_discordbot import logger
from discordbot.stocks.screener import screener_options as so
from gamestonk_terminal.stocks.screener.finviz_model import get_screener_data


async def technical_command(
    ctx, preset: str = "template", sort: str = "", limit: int = 5, ascend: bool = False
):
    """Displays stocks according to chosen preset, sorting by technical factors [Finviz]"""
    try:
        # Check for argument
        if preset == "template" or preset not in so.all_presets:
            raise Exception("Invalid preset selected!")

        # Debug
        if cfg.DEBUG:
            logger.debug(
                "!stocks.scr.technical %s %s %s %s", preset, sort, limit, ascend
            )

        # Check for argument
        if limit < 0:
            raise Exception("Number has to be above 0")

        # Output Data
        df_screen = get_screener_data(
            preset,
            "technical",
            limit,
            ascend,
        )

        description = ""

        if isinstance(df_screen, pd.DataFrame):
            if df_screen.empty:
                return []

            df_screen = df_screen.dropna(axis="columns", how="all")

            if sort:
                if " ".join(sort) in so.d_cols_to_sort["technical"]:
                    df_screen = df_screen.sort_values(
                        by=[" ".join(sort)],
                        ascending=ascend,
                        na_position="last",
                    )
                else:
                    similar_cmd = difflib.get_close_matches(
                        " ".join(sort),
                        so.d_cols_to_sort["technical"],
                        n=1,
                        cutoff=0.7,
                    )
                    if similar_cmd:
                        description = f"Replacing '{' '.join(sort)}' by '{similar_cmd[0]}' so table can be sorted.\n\n"
                        df_screen = df_screen.sort_values(
                            by=[similar_cmd[0]],
                            ascending=ascend,
                            na_position="last",
                        )
                    else:
                        raise ValueError(
                            f"Wrong sort column provided! Select from: {', '.join(so.d_cols_to_sort['technical'])}"
                        )

            df_screen = df_screen.fillna("")
            future_column_name = df_screen["Ticker"]
            df_screen = df_screen.head(n=limit).transpose()
            df_screen.columns = future_column_name
            df_screen.drop("Ticker")

            columns = []
            initial_str = description + "Overview"
            i = 1
            choices = [
                disnake.SelectOption(label="Overview", value="0", emoji="🟢"),
            ]
            for column in df_screen.columns.values:
                menu = f"\nPage {i}: {column}"
                initial_str += f"\nPage {i}: {column}"
                if i < 19:
                    choices.append(
                        disnake.SelectOption(label=menu, value=f"{i}", emoji="🟢"),
                    )
                if i == 20:
                    choices.append(
                        disnake.SelectOption(
                            label="Max Reached", value=f"{i}", emoji="🟢"
                        ),
                    )
                i += 1
            columns.append(
                disnake.Embed(
                    title="Stocks: [Finviz] Technical Screener",
                    description=initial_str,
                    colour=cfg.COLOR,
                ).set_author(
                    name=cfg.AUTHOR_NAME,
                    icon_url=cfg.AUTHOR_ICON_URL,
                )
            )
            for column in df_screen.columns.values:
                columns.append(
                    disnake.Embed(
                        title="Stocks: [Finviz] Technical Screener",
                        description="```"
                        + df_screen[column].fillna("").to_string()
                        + "```",
                        colour=cfg.COLOR,
                    ).set_author(
                        name=cfg.AUTHOR_NAME,
                        icon_url=cfg.AUTHOR_ICON_URL,
                    )
                )

            await ctx.send(embed=columns[0], view=Menu(columns, choices))

    except Exception as e:
        embed = disnake.Embed(
            title="ERROR Stocks: [Finviz] Technical Screener",
            colour=cfg.COLOR,
            description=e,
        )
        embed.set_author(
            name=cfg.AUTHOR_NAME,
            icon_url=cfg.AUTHOR_ICON_URL,
        )

        await ctx.send(embed=embed, delete_after=30.0)