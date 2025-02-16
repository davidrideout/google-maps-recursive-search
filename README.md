Google places api has an artificial limit of 60 results.

Brute force approach to overcoming the limit:
If a query to the api has 60 results, assume it has more--
recursively break the area down into hex grids using uber's 
h3 library. 

Works in theory...
