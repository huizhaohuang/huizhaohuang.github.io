from hormuz_energy import fetch_prices, main

fetch_prices(
    eia_key="anytXt8v6DjXCqI8mAHCGtrSadDhIMoRn5cQe5mO",
    fred_key="8c56aaa6bc2f21fc32a6ffb15628a575",
)
main("prices.csv")
