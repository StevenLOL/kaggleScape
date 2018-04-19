
# coding: utf-8

# <table>
#     <tr>
#         <td>
#         <center>
#         <font size="+1">If you haven't used BigQuery datasets on Kaggle previously, check out the <a href = "https://www.kaggle.com/rtatman/sql-scavenger-hunt-handbook/">Scavenger Hunt Handbook</a> kernel to get started.</font>
#         </center>
#         </td>
#     </tr>
# </table>
# 
# ___ 
# 
# ## Previous days:
# 
# * [**Day 1:** SELECT, FROM & WHERE](https://www.kaggle.com/rtatman/sql-scavenger-hunt-day-1/)
# * [**Day 2:** GROUP BY, HAVING & COUNT()](https://www.kaggle.com/rtatman/sql-scavenger-hunt-day-2/)
# * [**Day 3:** ORDER BY & Dates](https://www.kaggle.com/rtatman/sql-scavenger-hunt-day-3/)
# 
# ____
# 

# ## AS & WITH
# ___
# 
# So far we've learned how to use these clauses in our queries: 
# 
#     SELECT ... 
#     FROM ...
#     (WHERE) ...
#     GROUP BY ...
#     (HAVING) ...
#     ORDER BY
# By this point, our queries are getting pretty long, which can make them hard to puzzle out exactly what we're asking for.
# 
# We've also started using functions like EXTRACT() to get information out of dates or aggregate functions like COUNT(). You may have noticed, however, that the columns that we use these functions are are returned with names like `_f0` and `_f1`, which aren't very helpful.
# 
# Don't worry, though, we're going to learn how to get around both of these problems. Today, we're going to learn how to use AS and WITH to tidy up our queries and make them easier to read.
# 
# ### AS
# ___
# 
# First, let's talk about the AS clause. AS lets you refer to the the columns generated by your queries with different names, which is also know as "aliasing". (If you use Python a lot you might already have used `as` for aliasing if you've ever done something like `import pandas as pd` or `imports seaborn as sns`.)
# 
# To use AS in SQL, you just insert it right after the name of the column you select. Here's an example of a query **without** an AS clause:  
# 
#         SELECT EXTRACT(DAY FROM column_with_timestamp), data_point_3
#         FROM `bigquery-public-data.imaginary_dataset.imaginary_table`
# And here's an example of the same query, but with AS.
# 
#         SELECT EXTRACT(DAY FROM column_with_timestamp) AS day,
#                 data_point_3 AS data
#         FROM `bigquery-public-data.imaginary_dataset.imaginary_table`
# Both of these queries will return the exact same table, but in the second query the columns returned will be called `day` and `data`, rather than the default names of `_f0` and `data_point_3`.
# 
# ### WITH... AS
# ____
# 
# On its own, AS is a convenient way to make your code easier to read and tidy up the data returned by your query. It's even more powerful when combined with WITH in what's called a "common table expression" or CTE.
# 
# > **Common table expression**: A temporary table that you return within your query. You can then write queries against the new table you've created. CTE's only exist inside the query where you create them, though, so you can't reference them in later queries.
# 
# CTE's are very helpful for breaking up your queries into readable chunks and make it easier to follow what's going on in your code. 
# 
# Let's look at how to use them. We're going to be the same small Pets table that we've been working with previously, but now it includes information on the ages of all the different animals. These are in a column called "Years_old":
# 
# ![](https://i.imgur.com/01s9TwR.png)
# 
# We might want to ask questions about older animals in particular. One way that we could do this is to create a CTE that only contains information about older animals and then write get information about it. So we can create a CTE which only contains information about animals more than five years old like this:
# 
#     # note that this query won't return anything!
#     WITH Seniors AS 
#             (
#                 SELECT ID, Name
#                 FROM `bigquery-public-data.pet_records.pets`
#                 WHERE Years_old > 5
#             )
# This will create the following temporary table that we can then refer to in the rest of our query, which only has the ID and Name of the animals that are seniors:
# 
# ![](https://i.imgur.com/LBippKL.png)
# 
# If we wanted additional information about this table, we can write a query under it. So this query will create the CTE shown above, and then return all the ID's from it (in this case just 2 and 4).
# 
#     WITH Seniors AS 
#             (
#                 SELECT ID, Name
#                 FROM `bigquery-public-data.pet_records.pets`
#                 WHERE Years_old > 5
#             )
#     SELECT ID
#     FROM Seniors
# We could do this without a CTE, but if this were the first part of a very long query, removing the CTE would make it much harder to follow.

# ## Example: How many Bitcoin transactions are made per month?
# ____
# 
# Now let's work through an example with a real dataset. Today, we're going to be working with a Bitcoin dataset (Bitcoin is a popular but volatile cryptocurrency). We're going to use a common table expression (CTE) to find out how many Bitcoin transactions were made per month for the entire timespan of this dataset.
# 
# First, just like the last three days, we need to get our environment set up:

# In[ ]:


# import package with helper functions 
import bq_helper

# create a helper object for this dataset
bitcoin_blockchain = bq_helper.BigQueryHelper(active_project="bigquery-public-data",
                                              dataset_name="bitcoin_blockchain")


# Now we're going to write a query to get the number of transactions per month. One problem here is that this dataset uses timestamps rather than dates, and they're stored in this dataset as integers. We'll have to convert these into a format that BigQuery recognizes using TIMESTAMP_MILLIS(). We can do that using a CTE and then write a second part of the query against the new, temporary table we created. This has the advantage of breaking up our query into two, logical parts. 
# 
# * Convert the integer to a timestamp
# * Get information on the date of transactions from the timestamp
# 
# You can see the query I used to do this below.

# In[ ]:


query = """ WITH time AS 
            (
                SELECT TIMESTAMP_MILLIS(timestamp) AS trans_time,
                    transaction_id
                FROM `bigquery-public-data.bitcoin_blockchain.transactions`
            )
            SELECT COUNT(transaction_id) AS transactions,
                EXTRACT(MONTH FROM trans_time) AS month,
                EXTRACT(YEAR FROM trans_time) AS year
            FROM time
            GROUP BY year, month 
            ORDER BY year, month
        """

# note that max_gb_scanned is set to 21, rather than 1
transactions_per_month = bitcoin_blockchain.query_to_pandas_safe(query, max_gb_scanned=21)


# Since they're returned sorted, we can just plot the raw results to show us the number of Bitcoin transactions per month over the whole timespan of this dataset.

# In[ ]:


# import plotting library
import matplotlib.pyplot as plt

# plot monthly bitcoin transactions
plt.plot(transactions_per_month.transactions)
plt.title("Monthly Bitcoin Transcations")


# Pretty cool, huh? :)
# 
# As you can see, common table expressions let you shift a lot of your data cleaning into SQL. That's an especially good thing in the case of BigQuery because it lets you take advantage of BigQuery's parallelization, which means you'll get your results more quickly.

# # Scavenger hunt
# ___
# 
# > **Important note**: Today's dataset is bigger than the ones we've used previously, so your queries will be more than 1 Gigabyte. You can still run them by setting the "max_gb_scanned" argument in the `query_to_pandas_safe()` function to be large enough to run your query, or by using the `query_to_pandas()` function instead.
# 
# Now it's your turn! Here are the questions I would like you to get the data to answer. Practice using at least one alias in each query. 
# 
# * How many Bitcoin transactions were made each day in 2017?
#     * You can use the "timestamp" column from the "transactions" table to answer this question. You can check the [notebook from Day 3](https://www.kaggle.com/rtatman/sql-scavenger-hunt-day-3/) for more information on timestamps.
# * How many transactions are associated with each merkle root?
#     * You can use the "merkle_root" and "transaction_id" columns in the "transactions" table to answer this question. 
#     * Note that the earlier version of this question asked "How many *blocks* are associated with each merkle root?", which would be one block for each root. Apologies for the confusion!
# 
# In order to answer these questions, you can fork this notebook by hitting the blue "Fork Notebook" at the very top of this page (you may have to scroll up). "Forking" something is making a copy of it that you can edit on your own without changing the original.

# In[ ]:


# Your code goes here :)



# Please feel free to ask any questions you have in this notebook or in the [Q&A forums](https://www.kaggle.com/questions-and-answers)! 
# 
# Also, if you want to share or get comments on your kernel, remember you need to make it public first! You can change the visibility of your kernel under the "Settings" tab, on the right half of your screen.
